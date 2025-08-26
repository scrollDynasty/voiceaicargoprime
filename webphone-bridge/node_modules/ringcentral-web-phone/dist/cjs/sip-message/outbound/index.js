"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const index_js_1 = __importDefault(require("../index.js"));
class OutboundMessage extends index_js_1.default {
    static fromString(str) {
        const sipMessage = index_js_1.default.fromString(str);
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
exports.default = OutboundMessage;
