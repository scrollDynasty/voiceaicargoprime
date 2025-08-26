import OutboundMessage from "./index.js";
import type InboundMessage from "../inbound.js";
declare class ResponseMessage extends OutboundMessage {
    constructor(inboundMessage: InboundMessage, { responseCode, headers, body, }: {
        responseCode: number;
        headers?: {
            [key: string]: string;
        };
        body?: string;
    });
}
export default ResponseMessage;
