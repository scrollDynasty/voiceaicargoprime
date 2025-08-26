import OutboundMessage from "./index.js";
import responseCodes from "../response-codes.js";
class ResponseMessage extends OutboundMessage {
    constructor(inboundMessage, { responseCode, headers = {}, body = "", }) {
        super(undefined, { ...headers }, body);
        this.subject = `SIP/2.0 ${responseCode} ${responseCodes[responseCode]}`;
        const keys = ["Via", "From", "To", "Call-Id", "CSeq"];
        for (const key of keys) {
            if (inboundMessage.headers[key]) {
                this.headers[key] = inboundMessage.headers[key];
            }
        }
    }
}
export default ResponseMessage;
