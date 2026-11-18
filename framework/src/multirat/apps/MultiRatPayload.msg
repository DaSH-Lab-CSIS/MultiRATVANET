//
// MultiRatPayload - application payload of the vehicle-to-server traffic.
//
// Traffic is request-and-reply. A vehicle sends a request (a safety message, an
// infotainment chunk request, a probe) that says how many reply packets it wants and how big;
// the server sends them back to the address the request came from, i.e. over the same RAT.
//
// A request also carries what the receiving MultiRatSink needs to measure service quality and
// the real cost of a RAT switch: who sent it, on which RAT, and where the sender's current
// "epoch" (the time since its latest switch) began. A reply repeats the request's sequence
// number and send time, so the vehicle can tell how long the answer took.
//

import inet.common.INETDefs;
import inet.common.packet.chunk.Chunk;

namespace multiratvanet;

class MultiRatPayload extends inet::FieldsChunk
{
    bool reply = false;           // false: request (vehicle -> server); true: reply (server -> vehicle)
    int carId;                    // requesting node's module id
    long seq;                     // request: per-sender, per-app sequence number; reply: that of its request
    int rat = -1;                 // RatId the request was sent on (-1 = none)
    omnetpp::simtime_t requestTime; // when the request was sent
    // --- request only: the reply wanted
    int replyCount = 0;           // number of reply packets (0 = none)
    int replyLength = 0;          // bytes each
    omnetpp::simtime_t replyInterval; // spacing between them
    long switchCount;             // completed RAT switches of the sender (for this traffic class) at send time
    long epochStartSeq;           // seq of this app's first request sent after that switch
    omnetpp::simtime_t epochStartTime; // when that first request was sent
    // --- reply only
    int replyIndex = 0;           // 0 .. replyCount-1
}
