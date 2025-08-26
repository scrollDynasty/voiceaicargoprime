"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const index_js_1 = __importDefault(require("../sip-message/index.js"));
class InboundMessage extends index_js_1.default {
    static fromString(str) {
        const sipMessage = index_js_1.default.fromString(str);
        sipMessage.direction = "inbound";
        return sipMessage;
    }
}
exports.default = InboundMessage;
