//
// MultiRatProbeApp implementation. See MultiRatProbeApp.ned for the module description.
//

#include "MultiRatProbeApp.h"

#include <cmath>

#include "MultiRatPayload_m.h"
#include "manager/MultiRatAppManager.h"
#include "monitor/RatCoverageMonitor.h"

#include "inet/common/ModuleAccess.h"
#include "inet/common/TimeTag_m.h"
#include "inet/common/packet/Packet.h"
#include "inet/linklayer/common/InterfaceTag_m.h"
#include "inet/networklayer/common/L3AddressResolver.h"
#include "inet/networklayer/common/NextHopAddressTag_m.h"
#include "inet/networklayer/contract/ipv4/Ipv4Address.h"

namespace multiratvanet {

using namespace omnetpp;
using namespace inet;

Define_Module(MultiRatProbeApp);

MultiRatProbeApp::~MultiRatProbeApp()
{
    cancelAndDelete(probeTimer);
}

void MultiRatProbeApp::initialize(int stage)
{
    ApplicationBase::initialize(stage);

    if (stage == INITSTAGE_LOCAL) {
        destPort = par("destPort");
        probeInterval = par("probeInterval");
        window = par("window");
        echoTimeout = par("echoTimeout");
        manager = check_and_cast<MultiRatAppManager *>(getModuleByPath(par("managerModule").stringValue()));
        monitor = check_and_cast<RatCoverageMonitor *>(getModuleByPath(par("coverageMonitorModule").stringValue()));
        probeTimer = new cMessage("probe");
    }
}

void MultiRatProbeApp::handleStartOperation(LifecycleOperation *)
{
    socket.setOutputGate(gate("socketOut"));
    socket.setCallback(this);
    socket.bind(L3Address(), par("localPort"));
    // random phase, so cars that appear on the same SUMO time step do not probe in lockstep
    scheduleAt(simTime() + par("startTime").doubleValue() + uniform(0, probeInterval.dbl()), probeTimer);
}

void MultiRatProbeApp::handleMessageWhenUp(cMessage *msg)
{
    if (msg == probeTimer) {
        probeAll();
        scheduleAt(simTime() + probeInterval, probeTimer);
    }
    else
        socket.processMessage(msg);
}

// One probe on every RAT whose link is up, out of that RAT's own interface whatever the
// vehicle's traffic is using. The server echoes it to the address it came from.
void MultiRatProbeApp::probeAll()
{
    if (destAddr.isUnspecified())
        destAddr = L3AddressResolver().resolve(par("destAddress"));

    const RatMetricsVec& metrics = monitor->getMetrics();
    for (int i = 0; i < (int)RatId::COUNT && i < (int)metrics.size(); ++i) {
        publish(i);
        if (!metrics[i].present || !metrics[i].linked)
            continue;
        int interfaceId = -1;
        Ipv4Address gateway;
        if (!manager->getRatRoute((RatId)i, interfaceId, gateway))
            continue;

        const auto& payload = makeShared<MultiRatPayload>();
        payload->setChunkLength(B(par("probeLength")));
        payload->setCarId(getContainingNode(this)->getId());
        payload->setSeq(seq);
        payload->setRat(i);
        payload->setRequestTime(simTime());
        payload->setReplyCount(1);
        payload->setReplyLength(par("probeLength").intValue());
        payload->addTag<CreationTimeTag>()->setCreationTime(simTime());
        auto packet = new Packet("probe", payload);
        packet->addTag<InterfaceReq>()->setInterfaceId(interfaceId);
        if (!gateway.isUnspecified())
            packet->addTag<NextHopAddressReq>()->setNextHopAddress(gateway);
        socket.sendTo(packet, destAddr, destPort);

        Probe p;
        p.seq = seq++;
        p.sent = simTime();
        probes[i].recent.push_back(p);
        ++probes[i].sent;
    }
}

void MultiRatProbeApp::socketDataArrived(UdpSocket *, Packet *packet)
{
    auto payload = packet->peekAtFront<MultiRatPayload>();
    int rat = payload->getRat();
    if (payload->getReply() && rat >= 0 && rat < (int)RatId::COUNT) {
        RatProbes& rp = probes[rat];
        for (auto it = rp.recent.rbegin(); it != rp.recent.rend(); ++it) {
            if (it->seq == payload->getSeq()) {
                if (!it->echoed) {
                    it->echoed = true;
                    it->rttMs = (simTime() - it->sent).dbl() * 1e3;
                    rp.lastRttMs = it->rttMs;
                    rp.lastEchoTime = simTime().dbl();
                    ++rp.echoed;
                    rp.rttSumMs += it->rttMs;
                    publish(rat);
                }
                break;
            }
        }
    }
    delete packet;
}

// What the car now knows about this RAT from its probes, handed to the coverage monitor (which
// passes it to the policy): the last round trip, the mean over the window, and the share of
// probes lost among those old enough to be given up on.
void MultiRatProbeApp::publish(int rat)
{
    RatProbes& rp = probes[rat];
    simtime_t now = simTime();
    while (!rp.recent.empty() && rp.recent.front().sent < now - window - echoTimeout)
        rp.recent.pop_front();

    double rttSum = 0;
    int rttCount = 0, judged = 0, lost = 0;
    for (const Probe& p : rp.recent) {
        if (p.echoed && p.sent >= now - window) {
            rttSum += p.rttMs;
            ++rttCount;
        }
        if (p.echoed || p.sent <= now - echoTimeout) {
            ++judged;
            if (!p.echoed)
                ++lost;
        }
    }
    monitor->reportProbe((RatId)rat, rp.lastRttMs, rttCount > 0 ? rttSum / rttCount : NAN,
            judged > 0 ? (double)lost / judged : NAN, rp.lastEchoTime);
}

void MultiRatProbeApp::finish()
{
    for (int i = 0; i < (int)RatId::COUNT; ++i) {
        if (probes[i].sent == 0)
            continue;
        std::string base = ratName((RatId)i);
        recordScalar((base + ".probesSent").c_str(), probes[i].sent);
        recordScalar((base + ".probesEchoed").c_str(), probes[i].echoed);
        if (probes[i].echoed > 0)
            recordScalar((base + ".probeRttMean").c_str(), probes[i].rttSumMs / probes[i].echoed, "ms");
    }
    ApplicationBase::finish();
}

} // namespace multiratvanet
