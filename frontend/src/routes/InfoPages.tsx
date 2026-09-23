import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { SiteFooter } from '../components/SiteFooter'

export const CONTACT_EMAIL = 'CONTACT_EMAIL_TBD'
const UPDATED = '2026-09-23'

function InfoLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-paper">
      <header className="max-w-2xl mx-auto px-4 pt-8">
        <Link to="/" className="text-sm font-medium text-ink">← compa</Link>
      </header>
      <main className="max-w-2xl mx-auto px-4 py-8 text-sm leading-relaxed text-ink/70 space-y-4">
        <h1 className="text-2xl font-display font-normal text-ink">{title}</h1>
        {children}
        <p className="text-xs text-ink/70">Last updated {UPDATED}</p>
      </main>
      <SiteFooter />
    </div>
  )
}

const H = ({ children }: { children: ReactNode }) => (
  <h2 className="text-base font-display font-normal text-ink pt-4">{children}</h2>
)

const Mail = () => (
  <a href={`mailto:${CONTACT_EMAIL}`} className="underline">{CONTACT_EMAIL}</a>
)

export function AboutPage() {
  return (
    <InfoLayout title="About compa">
      <p>
        <strong>Luxury has its moment.</strong> compa tracks sale history for premium skincare
        and makeup across retailers and brand stores in Korea, the US, Japan and China, and
        tells you whether to buy now or wait — with the reason and the likely timing.
      </p>
      <p>
        We are not a coupon site. If waiting is the better call, we say so, even when a buy
        link would earn us a commission. Some outbound links are affiliate links (for example
        Amazon Associates); they never change a recommendation.
      </p>
      <H>한국어</H>
      <p>
        <strong>럭셔리엔 때가 있다.</strong> compa는 한·미·일·중 리테일러와 브랜드 공식몰의
        프리미엄 화장품 할인 이력을 모아, 지금 살지 기다릴지를 이유와 예상 시점과 함께
        알려줍니다. 기다리는 게 낫다면 제휴 수익이 있어도 "기다리세요"라고 말합니다.
      </p>
      <H>Contact / 문의</H>
      <p><Mail /></p>
    </InfoLayout>
  )
}

export function PrivacyPage() {
  return (
    <InfoLayout title="Privacy Policy">
      <p>compa has no user accounts and does not use analytics or advertising trackers.</p>
      <H>What we collect</H>
      <ul className="list-disc pl-5 space-y-1">
        <li>Search logs: the search text, number of results and time. Not linked to you.</li>
        <li>Feedback you send: the message, the page, and a contact address only if you enter one.</li>
        <li>
          Server logs: your IP address and requested URL, used for security, abuse prevention
          and rate limiting.
        </li>
        <li>
          Your browser's local storage keeps a premium access key if you enter one. It stays on
          your device.
        </li>
      </ul>
      <H>Third parties</H>
      <ul className="list-disc pl-5 space-y-1">
        <li>Cloudflare delivers the site and processes connection data.</li>
        <li>Google Fonts serves the site fonts and receives your IP address.</li>
        <li>jsDelivr serves the Korean font (Pretendard) and receives your IP address.</li>
        <li>
          Retailer and affiliate links (such as Amazon) take you to other sites, which may set
          their own cookies under their own policies.
        </li>
      </ul>
      <p>We do not sell personal information.</p>
      <H>Your choices</H>
      <p>To have feedback you sent deleted, or for any question, email <Mail />.</p>
      <H>한국어 요약</H>
      <p>
        compa는 회원가입이 없고 분석·광고 추적 도구를 쓰지 않습니다. 검색어·결과 수·시각,
        보내주신 피드백(연락처는 입력한 경우에만), 보안·과다요청 방지를 위한 서버 로그(IP)만
        처리합니다. 사이트는 Cloudflare로 전송되고 Google Fonts와 jsDelivr(Pretendard)를 사용하며, 제휴 링크(Amazon 등)로
        이동한 사이트는 자체 정책에 따라 쿠키를 쓸 수 있습니다. 개인정보를 판매하지 않습니다.
        삭제 요청·문의: <Mail />
      </p>
    </InfoLayout>
  )
}

export function TermsPage() {
  return (
    <InfoLayout title="Terms of Use">
      <ul className="list-disc pl-5 space-y-1">
        <li>
          compa is an information service. Prices, sale history and timing estimates are
          collected automatically and may be incomplete, delayed or wrong. Check the retailer
          before you buy.
        </li>
        <li>
          Purchases happen on retailer sites, under their terms. compa is not a party to them.
        </li>
        <li>
          Some links are affiliate links. compa may earn a commission at no extra cost to you.
          Commissions do not affect recommendations.
        </li>
        <li>Do not scrape or overload the service. We may limit abusive traffic.</li>
        <li>The service is provided as is, without warranty.</li>
      </ul>
      <H>한국어 요약</H>
      <p>
        compa는 정보 제공 서비스입니다. 가격·할인 이력·시점 예측은 자동 수집이라 틀리거나 늦을 수
        있으니 구매 전 판매처에서 확인하세요. 구매는 각 판매처 약관을 따르며, 일부 링크는 제휴
        링크지만 추천에는 영향을 주지 않습니다. 문의: <Mail />
      </p>
    </InfoLayout>
  )
}
