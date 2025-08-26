import SipMessage from "../sip-message/index.js";
declare class InboundMessage extends SipMessage {
    static fromString(str: string): InboundMessage;
}
export default InboundMessage;
