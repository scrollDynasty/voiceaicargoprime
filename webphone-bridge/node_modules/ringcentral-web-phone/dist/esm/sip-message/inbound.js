import SipMessage from "../sip-message/index.js";
class InboundMessage extends SipMessage {
    static fromString(str) {
        const sipMessage = SipMessage.fromString(str);
        sipMessage.direction = "inbound";
        return sipMessage;
    }
}
export default InboundMessage;
