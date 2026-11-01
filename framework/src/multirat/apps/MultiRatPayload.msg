//
// MultiRatPayload - application payload of MultiRatTrafficApp.
//
// Carries what the receiving MultiRatSink needs to measure service quality per
// traffic class and the real cost of a RAT switch: who sent it, on which RAT,
// and where the sender's current "epoch" (the time since its latest switch) began.
//

import inet.common.INETDefs;
import inet.common.packet.chunk.Chunk;

namespace multiratvanet;

class MultiRatPayload extends inet::FieldsChunk
{
    int carId;                    // sending node's module id
    long seq;                     // per-sender, per-app sequence number
    int rat = -1;                 // RatId active at send time (-1 = none)
    long switchCount;             // completed RAT switches of the sender at send time
    long epochStartSeq;           // seq of this app's first packet sent after that switch
    omnetpp::simtime_t epochStartTime; // when that first packet was sent
}
