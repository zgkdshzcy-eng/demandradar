/**
 * Web analytics: Google Analytics (international) + Baidu Tongji (China).
 *
 * Both are gated by env vars so dev / preview deployments stay clean. Tags load
 * with `afterInteractive` so they never block the LCP. Pageviews on the App
 * Router are fired from `<RouteAnalytics>` which listens to pathname changes.
 */
import Script from "next/script";

import { RouteAnalytics } from "./route-analytics";

const GA_ID = process.env.NEXT_PUBLIC_GA_ID || "";
const BAIDU_ID = process.env.NEXT_PUBLIC_BAIDU_ID || "";

export function Analytics() {
  if (!GA_ID && !BAIDU_ID) return null;
  return (
    <>
      {GA_ID ? (
        <>
          <Script
            id="ga-loader"
            strategy="afterInteractive"
            src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
          />
          <Script id="ga-init" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){window.dataLayer.push(arguments);}
              window.gtag = gtag;
              gtag('js', new Date());
              gtag('config', '${GA_ID}', { send_page_view: false });
            `}
          </Script>
        </>
      ) : null}
      {BAIDU_ID ? (
        <Script id="baidu-init" strategy="afterInteractive">
          {`
            var _hmt = _hmt || [];
            window._hmt = _hmt;
            (function() {
              var hm = document.createElement("script");
              hm.src = "https://hm.baidu.com/hm.js?${BAIDU_ID}";
              var s = document.getElementsByTagName("script")[0];
              s.parentNode.insertBefore(hm, s);
            })();
          `}
        </Script>
      ) : null}
      <RouteAnalytics gaId={GA_ID} baiduId={BAIDU_ID} />
    </>
  );
}
