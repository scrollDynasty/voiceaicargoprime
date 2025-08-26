import SipMessage from "../index.js";
class OutboundMessage extends SipMessage {
    static fromString(str) {
        const sipMessage = SipMessage.fromString(str);
        sipMessage.direction = "outbound";
        return sipMessage;
    }
    constructor(subject = "", headers = {}, body = "") {
        super(subject, headers, body);
        this.direction = "outbound";
        this.headers["Content-Length"] = this.body.length.toString();
        this.headers["User-Agent"] = "ringcentral-web-phone-2";
        this.headers["Max-Forwards"] = "70";
    }
}
export default OutboundMessage;
