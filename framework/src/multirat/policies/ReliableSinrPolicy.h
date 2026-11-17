//
// ReliableSinrPolicy.h - Sinr, upgraded: rank RATs by what actually gets through.
//
// Both traffic classes are judged on one thing: does the packet arrive in time. Every RAT
// already meets the latency budgets when it works, so what loses packets is a RAT that is not
// delivering. SINR is a proxy for that: it misses association loss, AP/RSU edges, collisions
// and backhaul. The car's own probes (10 per second on every linked RAT, echoed by the server)
// measure the whole path directly. So:
//
//   1. Reliability first. A RAT's reliability is the share of its probes that came back,
//      smoothed over the car's decisions (one 1 s window of 10 probes is +-0.13, too coarse to
//      compare RATs on), and halved if its probes put it over the latency budget. The top pick is
//      the most reliable usable RAT; within 'relTie' of each other, the larger SINR margin wins.
//   2. Sinr's hysteresis, guarded. Leave the current RAT only if the top pick is more reliable by
//      'relMargin', or about as reliable and 'marginDb' stronger (Sinr's own rule). Never move to
//      a less reliable RAT for signal. The change must hold for the time-to-trigger.
//   3. Fast fail. If the current RAT has stopped answering (no echo for 'failAge' beyond twice
//      its mean round trip, or half its recent probes lost), switch now to an answering RAT,
//      without the time-to-trigger: radio-link-failure detection from the car's own probes,
//      ahead of the harness dropping the RAT from range.
//   4. Hold-off. A RAT the car left because it failed or was lost is not considered again for
//      'holdOff' seconds, unless nothing else is usable. A RAT that has just failed has to prove
//      itself for longer; without this the car bounces back to a flickering RSU or a congested
//      channel as soon as the time-to-trigger allows.
//
// Inputs: inRange, linked, probeLoss, probeAge, probeRttMeanMs, sinrDb, minSinrDb. Nothing else.
//
#ifndef MULTIRATVANET_RELIABLESINRPOLICY_H
#define MULTIRATVANET_RELIABLESINRPOLICY_H

#include <cmath>

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class ReliableSinrPolicy : public TimeToTriggerPolicy {
  public:
    explicit ReliableSinrPolicy(double marginDb = 3.0, double maxLatencyMs = 100.0, double timeToTrigger = 1.0)
        : TimeToTriggerPolicy(timeToTrigger), marginDb_(marginDb), maxLatencyMs_(maxLatencyMs) {}

    RatId prefer(RatId current, const RatMetricsVec &metrics) const override {
        RatId top = topPick(metrics, heldOff(metrics));
        if (top == RatId::NONE || !usable(current, metrics) || top == current)
            return top;
        const RatMetrics &c = metrics[ratIndex(current)], &t = metrics[ratIndex(top)];
        double relGain = reliability(t) - reliability(c);
        bool moreReliable = relGain >= relMargin_;
        bool sameButStronger = relGain > -relTie_ && margin(t) >= margin(c) + marginDb_;
        return moreReliable || sameButStronger ? top : current;
    }

    RatId select(RatId current, const RatMetricsVec &metrics) override {
        RatId wanted = prefer(current, metrics);
        failing_ = wanted != current && usable(current, metrics) && usable(wanted, metrics) &&
                   failing(metrics[ratIndex(current)]) && answering(metrics[ratIndex(wanted)]);
        // a failing current RAT is treated as lost: the switch is made now
        bool currentOk = usable(current, metrics) && !failing_;
        RatId chosen = confirm_.apply(current, wanted, currentOk, metrics);
        if (!currentOk && chosen != current && current != RatId::NONE) {
            avoid_ = current;  // left because it failed: hold it off
            avoidUntil_ = now(metrics) + holdOff_;
        }
        return chosen;
    }

    PolicyResponse decide(const PolicyRequest &request) override {
        // the car's memory of each RAT's echo rate; forgotten while the RAT has no probes
        for (const RatMetrics &m : request.rats) {
            int i = ratIndex(m.id);
            if (i < 0 || i >= (int)RatId::COUNT)
                continue;
            if (std::isnan(m.probeLoss) || !m.linked)
                echoed_[i] = NAN;
            else
                echoed_[i] = std::isnan(echoed_[i]) ? 1.0 - m.probeLoss : echoed_[i] + smoothing_ * (1.0 - m.probeLoss - echoed_[i]);
        }
        PolicyResponse response = TimeToTriggerPolicy::decide(request);
        if (failing_) {
            const RatMetrics &c = request.rats[ratIndex(request.connection.currentRat)];
            char buf[64];
            snprintf(buf, sizeof buf, "%s no echo for %.2f s, %.0f%% lost", ratName(c.id), c.probeAge,
                     std::isnan(c.probeLoss) ? 0.0 : c.probeLoss * 100);
            response.branch = "failing";
            response.reason = buf;
        }
        else if (heldOff(request.rats) != RatId::NONE && response.rat != avoid_) {
            char buf[48];
            snprintf(buf, sizeof buf, "holding off %s for %.1f s", ratName(avoid_), avoidUntil_ - now(request.rats));
            response.reason += (response.reason.empty() ? "" : "; ") + std::string(buf);
        }
        return response;
    }

    const char *name() const override { return "ReliableSinr"; }

  protected:
    std::string marginNote(RatId current, RatId top, const RatMetricsVec &metrics) const override {
        const RatMetrics &c = metrics[ratIndex(current)], &t = metrics[ratIndex(top)];
        char buf[80];
        snprintf(buf, sizeof buf, "%+.0f%% echoed, %+.1f dB; needs +%.0f%% or +%g dB",
                 (reliability(t) - reliability(c)) * 100, margin(t) - margin(c), relMargin_ * 100, marginDb_);
        return buf;
    }

  private:
    // the RAT being held off now, if any other RAT is usable; NONE otherwise
    RatId heldOff(const RatMetricsVec &metrics) const {
        if (avoid_ == RatId::NONE || now(metrics) >= avoidUntil_)
            return RatId::NONE;
        for (const auto &m : metrics)
            if (m.present && m.inRange && m.id != avoid_)
                return avoid_;
        return RatId::NONE;
    }
    static double now(const RatMetricsVec &metrics) {
        double t = 0;
        for (const auto &m : metrics)
            t = std::max(t, m.lastUpdate);
        return t;
    }

    // the most reliable usable RAT (other than 'skip'); near-ties go to the larger SINR margin
    RatId topPick(const RatMetricsVec &metrics, RatId skip) const {
        RatId best = RatId::NONE;
        for (const auto &m : metrics) {
            if (!(m.present && m.inRange) || m.id == skip)
                continue;
            if (best == RatId::NONE) {
                best = m.id;
                continue;
            }
            const RatMetrics &b = metrics[ratIndex(best)];
            double d = reliability(m) - reliability(b);
            if (d >= relTie_ || (d > -relTie_ && margin(m) > margin(b)))
                best = m.id;
        }
        return best;
    }

    // share of probes echoed (smoothed), halved if the RAT is over the latency budget; 0.5 if unknown
    double reliability(const RatMetrics &m) const {
        int i = ratIndex(m.id);
        double e = i >= 0 && i < (int)RatId::COUNT ? echoed_[i] : NAN;
        double r = std::isnan(e) ? (std::isnan(m.probeLoss) ? 0.5 : 1.0 - m.probeLoss) : e;
        if (!std::isnan(m.probeRttMeanMs) && m.probeRttMeanMs / 2 > maxLatencyMs_)
            r *= 0.5;
        return r;
    }
    static double margin(const RatMetrics &m) { return m.sinrDb - m.minSinrDb; }
    bool failing(const RatMetrics &m) const {
        // silence is judged against the RAT's own round trip: 5G answers in tens of ms, DSRC in one
        double usual = std::isnan(m.probeRttMeanMs) ? 0.0 : 2 * m.probeRttMeanMs / 1000;
        return m.probeAge > failAge_ + usual || (!std::isnan(m.probeLoss) && m.probeLoss >= 0.5);
    }
    bool answering(const RatMetrics &m) const { return m.probeAge >= 0 && m.probeAge <= answerAge_; }

    double marginDb_;
    double maxLatencyMs_;
    double relMargin_ = 0.15;  // reliability gain that justifies a switch (2 probes in 10)
    double relTie_ = 0.05;     // reliabilities closer than this are equal
    double failAge_ = 0.25;    // s without an echo, beyond twice the mean round trip: stopped answering
    double answerAge_ = 0.15;  // s: a RAT echoed within this is answering
    double smoothing_ = 0.3;   // weight of the newest echo rate (about 3 decisions of memory)
    double echoed_[(int)RatId::COUNT] = { NAN, NAN, NAN, NAN, NAN };
    double holdOff_ = 2.0;     // s a RAT that failed is not considered again (2 x time-to-trigger)
    RatId avoid_ = RatId::NONE;
    double avoidUntil_ = 0;
    bool failing_ = false;     // the last select() switched at once because the current RAT failed
};

} // namespace multiratvanet

#endif
