import { v4 } from "uuid";
import md5 from "blueimp-md5";
export const uuid = () => v4();
export const branch = () => "z9hG4bK-" + uuid();
const generateResponse = (sipInfo, endpoint, nonce) => {
    const ha1 = md5(`${sipInfo.authorizationId}:${sipInfo.domain}:${sipInfo.password}`);
    const ha2 = md5(endpoint);
    const response = md5(`${ha1}:${nonce}:${ha2}`);
    return response;
};
export const generateAuthorization = (sipInfo, nonce, method) => {
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
export const withoutTag = (s) => s.replace(/;tag=.*$/, "");
export const extractAddress = (s) => s.match(/<(sip:.+?)>/)[1];
export const extractNumber = (s) => s.match(/<sip:(.+?)@/)[1];
export const extractTag = (peer) => peer.match(/;tag=(.*)/)[1];
export const fakeDomain = uuid() + ".invalid";
export const fakeEmail = uuid() + "@" + fakeDomain;
