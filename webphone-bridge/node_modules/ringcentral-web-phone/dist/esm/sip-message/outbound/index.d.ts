import SipMessage from "../index.js";
declare class OutboundMessage extends SipMessage {
    static fromString(str: string): OutboundMessage;
    constructor(subject?: string, headers?: {}, body?: string);
}
export default OutboundMessage;
