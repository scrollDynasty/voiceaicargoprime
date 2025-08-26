"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const index_js_1 = __importDefault(require("./index.js"));
const response_codes_js_1 = __importDefault(require("../response-codes.js"));
class ResponseMessage extends index_js_1.default {
    constructor(inboundMessage, { responseCode, headers = {}, body = "", }) {
        super(undefined, { ...headers }, body);
        this.subject = `SIP/2.0 ${responseCode} ${response_codes_js_1.default[responseCode]}`;
        const keys = ["Via", "From", "To", "Call-Id", "CSeq"];
        for (const key of keys) {
            if (inboundMessage.headers[key]) {
                this.headers[key] = inboundMessage.headers[key];
            }
        }
    }
}
exports.default = ResponseMessage;
