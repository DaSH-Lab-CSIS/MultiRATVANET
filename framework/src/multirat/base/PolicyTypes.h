//
// PolicyTypes.h - the standard request and response of a RAT selection policy.
//
// On every decision the simulator hands the policy of one vehicle a PolicyRequest and gets back a
// PolicyResponse (the RAT to use). The request holds only what that vehicle knows by itself: its
// own position, its connection, and what its own radios measure. Nothing about other vehicles,
// and nothing only the infrastructure or the server could know.
// docs/POLICY_REFERENCE.md describes every field, its unit and where its value comes from.
//
// Like RatTypes.h these types have no OMNeT++/INET dependency, so a policy can be compiled and
// tested without the simulator.
//
#ifndef MULTIRATVANET_POLICYTYPES_H
#define MULTIRATVANET_POLICYTYPES_H

#include <map>
#include <string>
#include <vector>

#include "base/RatTypes.h"

namespace multiratvanet {

// Who is asking, and where it is.
struct VehicleState {
    int id = -1;               // unique per run and never reused: index of the car in the simulation
    std::string externalId;    // the vehicle's id in SUMO ("" if the vehicle is not driven by SUMO)
    double x = 0, y = 0, z = 0;   // position (m), simulation frame
    double vx = 0, vy = 0;     // velocity (m/s), simulation frame
    double speed = 0;          // m/s
    double heading = 0;        // direction of travel (rad, atan2(vy, vx)); 0 when standing still
};

// What the vehicle is connected through, and its switching history.
struct ConnectionState {
    RatId currentRat = RatId::NONE;    // the vehicle's default RAT (PolicyResponse::rat); NONE before the first attach
    RatId previousRat = RatId::NONE;   // RAT used before the current one
    double timeOnCurrentRat = 0;       // s since the current RAT became active
    long switchCount = 0;              // completed switches so far
    long pingPongCount = 0;            // of those, returns to the previous RAT within the ping-pong window
    bool switchInProgress = false;     // a switch has started and not finished (only with an extra switch delay);
                                       // a different RAT returned now is ignored
    RatId pendingRat = RatId::NONE;    // its target
};

// What became of the response to the previous request.
enum class DecisionOutcome {
    NONE = 0,              // there was no previous request
    KEPT = 1,              // the response named the current RAT (or NONE): nothing changed
    ATTACHED = 2,          // first RAT of this vehicle taken into use
    SWITCH_COMPLETED = 3,  // the vehicle moved to the requested RAT
    SWITCH_PENDING = 4,    // the switch started and is still waiting out the extra switch delay
    SWITCH_FAILED = 5,     // the requested RAT could not be taken into use (left coverage, no interface)
    REJECTED = 6,          // the requested RAT was not in range at decision time; nothing was done
    IGNORED = 7            // a switch was already in progress; nothing was done
};

inline const char *outcomeName(DecisionOutcome o) {
    switch (o) {
        case DecisionOutcome::NONE:             return "NONE";
        case DecisionOutcome::KEPT:             return "KEPT";
        case DecisionOutcome::ATTACHED:         return "ATTACHED";
        case DecisionOutcome::SWITCH_COMPLETED: return "SWITCH_COMPLETED";
        case DecisionOutcome::SWITCH_PENDING:   return "SWITCH_PENDING";
        case DecisionOutcome::SWITCH_FAILED:    return "SWITCH_FAILED";
        case DecisionOutcome::REJECTED:         return "REJECTED";
        case DecisionOutcome::IGNORED:          return "IGNORED";
        default:                                return "?";
    }
}

struct PreviousDecision {
    RatId requestedRat = RatId::NONE;                 // PolicyResponse::rat of the previous request
    DecisionOutcome outcome = DecisionOutcome::NONE;
};

// What the vehicle has seen of one of its traffic classes. Traffic is request-and-reply: the
// vehicle sends requests (a safety message, an infotainment chunk request) and the server
// answers each over the RAT it arrived on. The replies are all the vehicle knows of how the
// class is doing.
struct TrafficCounters {
    long requests = 0;          // requests the vehicle sent
    long repliesExpected = 0;   // reply packets those requests asked for
    long repliesReceived = 0;   // reply packets that arrived
    double delaySum = 0;        // s, sum over the received replies of (arrival - sending of their request)
    double delayMax = 0;        // s
};

struct TrafficState {
    std::string trafficClass;        // e.g. "safety", "infotainment"
    RatId rat = RatId::NONE;         // RAT this class is sent on now
    long switchCount = 0;            // times this class has changed RAT
    TrafficCounters window;          // since the previous request to the policy
    TrafficCounters total;           // since the vehicle appeared
};

// What one vehicle knows at one decision.
struct PolicyRequest {
    long sequence = 0;            // number of this request for this vehicle, from 0
    double time = 0;              // simulation time (s)
    double decisionInterval = 0;  // s between requests, as configured
    VehicleState vehicle;
    ConnectionState connection;
    RatMetricsVec rats;           // one entry per RatId, indexed by ratIndex()
    PreviousDecision previous;
    std::vector<TrafficState> traffic;   // one entry per traffic class of the vehicle
};

// What a policy answers: a RAT for each traffic class of the vehicle.
struct PolicyResponse {
    RatId rat = RatId::NONE;   // RAT for every class not named in classRat; NONE or the current RAT = stay
    std::map<std::string, RatId> classRat;   // optional: a different RAT for a class, by class name
    std::string reason;        // optional free text, written to the simulation log

    PolicyResponse() {}
    PolicyResponse(RatId r, const std::string &why = "") : rat(r), reason(why) {}
};

} // namespace multiratvanet

#endif
