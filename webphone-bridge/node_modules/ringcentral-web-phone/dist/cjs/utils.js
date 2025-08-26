"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.fakeEmail = exports.fakeDomain = exports.extractTag = exports.extractNumber = exports.extractAddress = exports.withoutTag = exports.generateAuthorization = exports.branch = exports.uuid = void 0;
const uuid_1 = require("uuid");
const blueimp_md5_1 = __importDefault(require("blueimp-md5"));
const uuid = () => (0, uuid_1.v4)();
exports.uuid = uuid;
const branch = () => "z9hG4bK-" + (0, exports.uuid)();
exports.branch = branch;
const generateResponse = (sipInfo, endpoint, nonce) => {
    const ha1 = (0, blueimp_md5_1.default)(`${sipInfo.authorizationId}:${sipInfo.domain}:${sipInfo.password}`);
    const ha2 = (0, blueimp_md5_1.default)(endpoint);
    const response = (0, blueimp_md5_1.default)(`${ha1}:${nonce}:${ha2}`);
    return response;
};
const generateAuthorization = (sipInfo, nonce, method) => {
    const authObj = {
        "Digest algorithm": "MD5",
        username: sipInfo.authorizationId,
        realm: sipInfo.domain,
        nonce,
        uri: `sip:${sipInfo.domain}`,
        response: generateResponse(sipInfo, `${method}:sip:${sipInfo.domain}`, nonce),
    };
    return Object.keys(authObj)
        .map((key) => `${key}="${authObj[key]}"`)
        .join(", ");
};
exports.generateAuthorization = generateAuthorization;
const withoutTag = (s) => s.replace(/;tag=.*$/, "");
exports.withoutTag = withoutTag;
const extractAddress = (s) => s.match(/<(sip:.+?)>/)[1];
exports.extractAddress = extractAddress;
const extractNumber = (s) => s.match(/<sip:(.+?)@/)[1];
exports.extractNumber = extractNumber;
const extractTag = (peer) => peer.match(/;tag=(.*)/)[1];
exports.extractTag = extractTag;
exports.fakeDomain = (0, exports.uuid)() + ".invalid";
exports.fakeEmail = (0, exports.uuid)() + "@" + exports.fakeDomain;
