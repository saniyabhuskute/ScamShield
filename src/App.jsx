import { useEffect, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  Globe2,
  HeartHandshake,
  Languages,
  LockKeyhole,
  Menu,
  MessageSquareText,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'

const NAV = [
  { id: 'scanner', label: 'Message Scanner', icon: ScanSearch, number: '01' },
  { id: 'intelligence', label: 'Risk Intelligence', icon: Sparkles, number: '02' },
  { id: 'insights', label: 'Security Insights', icon: Activity, number: '03' },
]

function App() {
  const [active, setActive] = useState('scanner')
  const [message, setMessage] = useState('')
  const [language, setLanguage] = useState('auto')
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [summary, setSummary] = useState({ total: 0, high: 0, medium: 0, low: 0, feedback_total: 0 })
  const [apiState, setApiState] = useState('checking')
  const [loading, setLoading] = useState(false)
  const [scanNotice, setScanNotice] = useState('')
  const [error, setError] = useState('')
  const [mobileNav, setMobileNav] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [feedbackSent, setFeedbackSent] = useState(false)

  async function refreshDashboard() {
    const [scansResponse, insightsResponse, healthResponse] = await Promise.all([
      fetch('/api/scans?limit=100'), fetch('/api/insights'), fetch('/api/health'),
    ])
    if (!scansResponse.ok || !insightsResponse.ok || !healthResponse.ok) throw new Error('ScamShield API is unavailable.')
    const [scans, insights, health] = await Promise.all([
      scansResponse.json(), insightsResponse.json(), healthResponse.json(),
    ])
    setHistory(scans.scans || [])
    setSummary(insights)
    setApiState(health.status === 'ok' ? 'online' : 'degraded')
  }

  async function responseError(response, fallback) {
    try {
      const payload = await response.json()
      return typeof payload.detail === 'string' ? payload.detail : fallback
    } catch {
      return fallback
    }
  }

  useEffect(() => {
    refreshDashboard().catch(() => setApiState('offline'))
  }, [])

  async function handleScan(event) {
    event.preventDefault()
    if (!message.trim()) {
      setError('Paste a message first, and we’ll check it for you.')
      return
    }
    setLoading(true)
    setError('')
    setScanNotice('')
    setFeedback('')
    setFeedbackSent(false)
    const mayNeedTranslation = language !== 'en' && (language !== 'auto' || /[^\x00-\x7f]/.test(message))
    const translationNoticeTimer = mayNeedTranslation
      ? window.setTimeout(() => setScanNotice('Translation can take longer on first use. A first Marathi scan downloads its local model; later scans should be faster.'), 8000)
      : null
    try {
      const response = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, language }),
      })
      if (!response.ok) throw new Error(await responseError(response, 'The scan service could not process this message. Try again.'))
      const scan = await response.json()
      setResult(scan)
      try {
        await refreshDashboard()
      } catch {
        setApiState('offline')
        setError('The scan was saved, but the dashboard could not refresh. Your saved result is still shown.')
      }
    } catch (err) {
      setError(err.message === 'Failed to fetch' ? 'Can’t reach the ScamShield API. Make sure the FastAPI server is running.' : err.message)
    } finally {
      if (translationNoticeTimer !== null) window.clearTimeout(translationNoticeTimer)
      setScanNotice('')
      setLoading(false)
    }
  }

  async function saveFeedback() {
    if (!feedback || !result) return
    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scan_id: result.id, helpful: feedback }),
      })
      if (!response.ok) throw new Error(await responseError(response, 'Could not save feedback.'))
      setFeedbackSent(true)
      await refreshDashboard()
    } catch (err) {
      setError(err.message === 'Failed to fetch' ? 'Could not reach the API to save feedback. Please try again.' : err.message)
    }
  }

  function navigate(id) {
    setActive(id)
    setMobileNav(false)
  }

  return (
    <div className="min-h-screen bg-canvas text-ink">
      {mobileNav && <button className="fixed inset-0 z-30 bg-ink/25 md:hidden" aria-label="Close menu" onClick={() => setMobileNav(false)} />}
      <aside className={`sidebar fixed inset-y-0 left-0 z-40 flex w-[258px] flex-col border-r border-[#e4e1ee] bg-[#f0eef7] px-5 py-6 transition-transform md:translate-x-0 ${mobileNav ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="mb-10 flex items-center justify-between px-1">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-violet text-white shadow-lg shadow-violet/20"><ShieldCheck size={23} strokeWidth={2.3} /></div>
            <div><div className="font-display text-[17px] font-extrabold leading-tight">ScamShield</div><div className="mt-1 text-[11px] text-[#85879a]">A calmer way to check</div></div>
          </div>
          <button className="rounded-lg p-2 text-muted md:hidden" aria-label="Close navigation" onClick={() => setMobileNav(false)}><X size={18} /></button>
        </div>

        <div className="mb-3 px-2 text-[10px] font-bold uppercase tracking-[.16em] text-[#9999a9]">Workspace</div>
        <nav className="space-y-1.5">
          {NAV.map(({ id, label, icon: Icon, number }) => (
            <button key={id} onClick={() => navigate(id)} className={`group flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-[13px] font-semibold transition ${active === id ? 'bg-white/80 text-violet shadow-sm' : 'text-[#707386] hover:bg-white/50 hover:text-ink'}`}>
              <Icon size={17} strokeWidth={2} /> <span className="flex-1">{label}</span><span className={`text-[10px] ${active === id ? 'text-violet/60' : 'text-[#b1b1bd]'}`}>{number}</span>
            </button>
          ))}
        </nav>

        <div className="mt-auto rounded-2xl border border-[#e5e2f0] bg-[#f8f7fb] p-4">
          <div className="flex items-center gap-2 text-[12px] font-bold text-[#4d4b65]"><LockKeyhole size={14} className="text-violet" /> Your messages stay yours</div>
          <p className="mb-0 mt-2 text-[11px] leading-relaxed text-[#85879a]">Scans are saved locally. Hindi uses your configured translation service; Marathi uses a local translation model.</p>
        </div>
        <div className="px-2 pt-4 text-[10px] text-[#9999a9]">ScamShield · Preview build</div>
      </aside>

      <div className="min-h-screen md:pl-[258px]">
        <header className="sticky top-0 z-20 flex h-[68px] items-center justify-between border-b border-line/80 bg-canvas/90 px-5 backdrop-blur md:px-10">
          <div className="flex items-center gap-3">
            <button className="rounded-xl border border-line bg-card p-2 text-muted md:hidden" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu size={18} /></button>
            <div className="hidden items-center gap-2 text-[12px] text-muted sm:flex"><span>ScamShield</span><ChevronRight size={13} /><span className="font-semibold text-ink">{NAV.find((item) => item.id === active)?.label}</span></div>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-line bg-card px-3 py-2 text-[11px] font-medium text-[#777b8e]"><span className={`h-2 w-2 rounded-full ${apiState === 'online' ? 'bg-[#71a88f]' : apiState === 'checking' ? 'bg-[#d6a16e]' : 'bg-[#c87979]'}`} />{apiState === 'online' ? 'API connected' : apiState === 'checking' ? 'Connecting…' : apiState === 'degraded' ? 'API degraded' : 'API unavailable'}</div>
        </header>

        <main className="mx-auto max-w-[1330px] px-5 py-8 md:px-10 md:py-10">
          {active === 'scanner' && <Scanner message={message} setMessage={setMessage} language={language} setLanguage={setLanguage} onScan={handleScan} loading={loading} scanNotice={scanNotice} error={error} result={result} />}
          {active === 'intelligence' && <Intelligence />}
          {active === 'insights' && <Insights history={history} counts={summary} feedback={feedback} setFeedback={setFeedback} feedbackSent={feedbackSent} saveFeedback={saveFeedback} />}
        </main>
      </div>
    </div>
  )
}

function PageHeading({ eyebrow, title, description }) {
  return <div className="mb-8"><div className="mb-2 text-[10px] font-extrabold uppercase tracking-[.16em] text-violet">{eyebrow}</div><h1 className="font-display text-[32px] font-extrabold leading-tight tracking-[-.045em] text-ink md:text-[39px]">{title}</h1><p className="mb-0 mt-2 max-w-2xl text-[14px] leading-relaxed text-muted">{description}</p></div>
}

function Scanner({ message, setMessage, language, setLanguage, onScan, loading, scanNotice, error, result }) {
  return <>
    <PageHeading eyebrow="Module 01 · Smart Message Scanner" title="Check a message, calmly." description="Paste a suspicious SMS, chat, or email. We’ll help you understand the warning signs." />
    <div className="grid gap-5 xl:grid-cols-[1.45fr_1fr]">
      <section className="rounded-[22px] border border-line bg-card p-5 shadow-soft md:p-7">
        <div className="mb-5 flex items-start justify-between gap-3"><div><h2 className="font-display text-[16px] font-extrabold">Message to check</h2><p className="mb-0 mt-1 text-[12px] text-muted">Scans are saved locally when you press Scan message.</p></div><div className="hidden rounded-xl bg-lavender p-2.5 text-violet sm:block"><MessageSquareText size={19} /></div></div>
        <form onSubmit={onScan}>
          <label htmlFor="message" className="sr-only">Message to check</label>
          <textarea id="message" value={message} onChange={(event) => setMessage(event.target.value)} maxLength={10000} placeholder={'Paste the message here…\n\nExample: Your account will be blocked today. Verify your details at http://…'} className="h-[190px] w-full resize-y rounded-2xl border border-[#e6e3dc] bg-[#f9f8f5] p-4 text-[13px] leading-relaxed text-ink outline-none transition placeholder:text-[#a1a2ad] focus:border-violet/50 focus:ring-4 focus:ring-violet/10" />
          <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="w-full sm:max-w-[220px]"><label htmlFor="language" className="mb-2 block text-[11px] font-bold text-[#66697a]">Message language</label><div className="relative"><Globe2 size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><select id="language" value={language} onChange={(event) => setLanguage(event.target.value)} className="w-full appearance-none rounded-xl border border-[#e6e3dc] bg-[#f9f8f5] py-2.5 pl-9 pr-3 text-[12px] text-ink outline-none focus:border-violet/50"><option value="auto">Auto-detect</option><option value="en">English</option><option value="hi">हिंदी · Hindi</option><option value="mr">मराठी · Marathi</option></select></div></div>
            <div className="flex items-center gap-2 text-[11px] text-muted"><Languages size={15} className="text-violet" /> English · हिंदी · मराठी</div>
          </div>
          {error && <div role="alert" className="mt-4 rounded-xl border border-[#efd8d7] bg-[#fff3f1] px-3.5 py-3 text-[12px] text-[#a55050]">{error}</div>}
          <button disabled={loading} type="submit" className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-violet px-4 py-3 text-[13px] font-bold text-white shadow-lg shadow-violet/20 transition hover:bg-[#6559b4] disabled:cursor-wait disabled:opacity-70 sm:w-auto sm:min-w-[180px]">{loading ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" /> {scanNotice ? 'Preparing translation…' : 'Checking message…'}</> : <><Sparkles size={16} /> Scan message <ArrowRight size={15} /></>}</button>
          {scanNotice && <p role="status" className="mt-2 text-[11px] leading-relaxed text-muted">{scanNotice}</p>}
        </form>
      </section>

      <section className="rounded-[22px] border border-line bg-card p-5 shadow-soft md:p-7">
        <div className="mb-4 flex items-center gap-2"><div className="rounded-xl bg-mint p-2.5 text-[#478a70]"><HeartHandshake size={18} /></div><h2 className="font-display text-[16px] font-extrabold">A thoughtful check</h2></div>
        <p className="mb-5 text-[12px] leading-relaxed text-muted">ScamShield looks for a few different clues and explains what caught its attention.</p>
        <div className="space-y-0">
          <Step number="01" title="Language-aware" body="Choose a language or let the app try to identify it." />
          <Step number="02" title="Message analysis" body="A text classifier and independent warning signals are combined." />
          <Step number="03" title="Clear next steps" body="See the reasons and practical safety advice." last />
        </div>
        <div className="mt-5 flex items-start gap-2 rounded-xl bg-[#f5f3ef] p-3.5 text-[11px] leading-relaxed text-[#7c7d8b]"><CircleHelp size={15} className="mt-0.5 shrink-0 text-violet" />Never share an OTP, password, PIN, or card details in response to a message.</div>
      </section>
    </div>
    {result && <ResultCard result={result} />}
  </>
}

function Step({ number, title, body, last }) {
  return <div className={`flex gap-3.5 py-3 ${last ? '' : 'border-b border-[#f0eee8]'}`}><div className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-lavender text-[10px] font-extrabold text-violet">{number}</div><div><div className="text-[12px] font-bold text-[#404253]">{title}</div><div className="mt-1 text-[11px] leading-relaxed text-[#858698]">{body}</div></div></div>
}

function ResultCard({ result }) {
  const config = {
    High: { label: 'Review carefully', icon: ShieldAlert, className: 'bg-[#f8e9e9] text-[#aa5353]', bar: 'bg-[#c87979]' },
    Medium: { label: 'Some warning signs', icon: AlertTriangle, className: 'bg-peach text-[#a36d36]', bar: 'bg-[#d6a16e]' },
    Low: { label: 'Fewer warning signs', icon: Check, className: 'bg-mint text-[#3e7b62]', bar: 'bg-[#70a58c]' },
  }[result.risk]
  const Icon = config.icon
  const hasScore = typeof result.score === 'number' && Number.isFinite(result.score)
  const complete = result.mode === 'model' || result.mode === 'demo'
  const modelConflict = result.mode === 'model' && result.model_label === 'legitimate' && result.risk !== 'Low'
  return <section className="mt-6 scroll-mt-24" aria-live="polite"><div className="mb-3 text-[10px] font-extrabold uppercase tracking-[.16em] text-violet">Your scan result</div><div className="grid gap-5 lg:grid-cols-2">
    <div className="rounded-[22px] border border-line bg-card p-6 shadow-soft"><div className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-wide ${config.className}`}><Icon size={13} />{complete ? `${result.risk} risk` : 'Check incomplete'}</div><h2 className="mt-3 font-display text-[22px] font-extrabold">{complete ? config.label : 'Could not fully assess'}</h2><p className="mt-1 text-[12px] leading-relaxed text-muted">{complete ? (result.mode === 'model' ? 'The classifier estimate is combined with independent warning signals.' : 'This uses preview rules only, not your trained Transformer model.') : 'Some checks could not run. Treat this message with care and review the available signals.'}</p>{result.mode === 'model' && <><div className={`mt-4 inline-flex rounded-lg px-3 py-2 text-[11px] font-bold ${result.model_label === 'scam' ? 'bg-[#f8e9e9] text-[#aa5353]' : modelConflict ? 'bg-peach text-[#a36d36]' : 'bg-mint text-[#3e7b62]'}`}>Model estimate: {result.model_label === 'scam' ? 'Likely scam' : 'Likely legitimate'}</div>{modelConflict && <p className="mt-2 rounded-xl bg-peach/60 px-3 py-2 text-[11px] leading-relaxed text-[#875c32]">Independent warning signals raised the overall risk to {result.risk}. Treat those signs seriously even though the model gave this message a lower scam score.</p>}</>}<div className="mt-6 flex items-center justify-between text-[11px] text-muted"><span>{hasScore ? 'Estimated scam score' : 'Scam score'}</span><strong className="text-[13px] text-ink">{hasScore ? `${Math.round(result.score * 100)}%` : 'Unavailable'}</strong></div>{hasScore && <><div className="mt-2 h-2 overflow-hidden rounded-full bg-[#efedf2]"><div className={`h-full rounded-full ${config.bar}`} style={{ width: `${Math.round(result.score * 100)}%` }} /></div></>}{result.urls?.length > 0 && <div className="mt-4 flex flex-wrap gap-2">{result.urls.map((url) => <span key={url} className="inline-flex max-w-full items-center gap-1 truncate rounded-lg bg-[#f5f3ef] px-2.5 py-1.5 text-[10px] text-muted"><Globe2 size={12} />{url}</span>)}</div>}</div>
    <div className="rounded-[22px] border border-line bg-card p-6 shadow-soft"><h3 className="font-display text-[15px] font-extrabold">What stood out</h3><div className="mt-2">{result.signals.length ? result.signals.map((signal) => <div key={signal} className="flex gap-2.5 border-b border-[#f0eee8] py-3 text-[12px] text-[#515466] last:border-0"><span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[#d39154]" />{signal}</div>) : <div className="py-4 text-[12px] leading-relaxed text-muted">{complete ? 'No common warning pattern was found in this preview check.' : 'No warning signals were identified, but this was not a full analysis.'}</div>}</div></div>
  </div>{result.translated_message && <div className="mt-5 rounded-2xl border border-[#e5e2f0] bg-[#f8f7fb] p-4 text-[12px] leading-relaxed text-[#515466]"><strong className="mb-1 block text-[10px] font-extrabold uppercase tracking-[.12em] text-violet">English translation · used for analysis</strong>{result.translated_message}</div>}{result.safe_reply_coach?.length ? <div className="mt-5 flex gap-3 rounded-2xl border border-[#dcebe4] bg-[#eaf3ef] p-4 text-[12px] leading-relaxed text-[#416a59]"><div className="mt-0.5 rounded-lg bg-white/70 p-1.5"><LockKeyhole size={15} /></div><div className="min-w-0"><strong className="mb-2 block text-[#35614e]">Safe Reply Coach</strong><ol className="space-y-2 pl-4">{result.safe_reply_coach.map((step, index) => <li key={index} className="pl-1">{step}</li>)}</ol></div></div> : <div className="mt-5 flex gap-3 rounded-2xl border border-[#dcebe4] bg-[#eaf3ef] p-4 text-[12px] leading-relaxed text-[#416a59]"><div className="mt-0.5 rounded-lg bg-white/70 p-1.5"><LockKeyhole size={15} /></div><div><strong className="mb-1 block text-[#35614e]">What you can do</strong>{result.recommendation || 'Don’t reply, open links, or share codes or payment details. Contact the organization through its official app or a number you find independently.'}</div></div>}<p className="mt-3 text-[10px] text-[#9698a5]">{result.notice} {hasScore && 'A low score does not prove a message is safe.'}</p></section>
}

function Intelligence() {
  const cards = [
    { icon: Sparkles, label: 'MODEL ESTIMATE', title: 'Scam classification', body: 'A fine-tuned Transformer estimates whether the message resembles scam examples.', tone: 'bg-lavender text-violet' },
    { icon: ScanSearch, label: 'INDEPENDENT SIGNALS', title: 'Risk fusion', body: 'Urgency, threats, requests for codes or payment, and risky links add context.', tone: 'bg-peach text-[#a36d36]' },
    { icon: HeartHandshake, label: 'HUMAN-READABLE', title: 'Reasons and advice', body: 'The result explains what triggered concern and suggests safe next steps.', tone: 'bg-mint text-[#478a70]' },
  ]
  return <><PageHeading eyebrow="Module 02 · Explainable Risk Intelligence" title="Understand the warning signs." description="A clear look at how a message can be assessed, with reasons you can act on." /><div className="grid gap-4 lg:grid-cols-3">{cards.map(({ icon: Icon, label, title, body, tone }) => <div key={title} className="rounded-[20px] border border-line bg-card p-5 shadow-soft"><div className={`mb-4 inline-flex rounded-xl p-2.5 ${tone}`}><Icon size={18} /></div><div className="text-[9px] font-extrabold tracking-[.14em] text-muted">{label}</div><h2 className="mt-2 font-display text-[15px] font-extrabold">{title}</h2><p className="mb-0 mt-2 text-[12px] leading-relaxed text-muted">{body}</p></div>)}</div><div className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_1fr]"><div className="rounded-[22px] border border-line bg-card p-6 shadow-soft"><h2 className="font-display text-[16px] font-extrabold">Signals checked</h2><div className="mt-3 space-y-0">{['Urgency and threats, such as an account being blocked', 'Requests for OTPs, PINs, passwords, or payment', 'Suspicious URL patterns and links', 'Classifier estimate, considered alongside message context'].map((signal) => <div key={signal} className="flex gap-2.5 border-b border-[#f0eee8] py-3 text-[12px] text-[#515466] last:border-0"><span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[#d39154]" />{signal}</div>)}</div></div><div className="rounded-[22px] border border-[#e5e2f0] bg-[#f8f7fb] p-6"><h2 className="font-display text-[16px] font-extrabold">How to read the score</h2><p className="mt-3 text-[12px] leading-relaxed text-muted">The score is an estimate, not a calibrated probability. A low score does not prove a message is safe, and a high score is not proof of fraud.</p><div className="my-4 h-px bg-[#e7e4ed]" /><p className="mb-0 text-[12px] leading-relaxed text-muted">Messages in English are analyzed directly. Hindi and Marathi messages are translated locally before classification, with language uncertainty shown clearly.</p></div></div></>
}

function Insights({ history, counts, feedback, setFeedback, feedbackSent, saveFeedback }) {
  const total = counts.total ?? 0
  const metrics = [
    { label: 'Messages scanned', value: total, foot: 'Saved locally', icon: MessageSquareText, tone: 'bg-lavender text-violet' },
    { label: 'High-risk flags', value: counts.high, foot: 'Review flagged messages carefully', icon: ShieldAlert, tone: 'bg-[#f8e9e9] text-[#aa5353]' },
    { label: 'Lower-risk results', value: counts.low, foot: 'Fewer signals found', icon: Check, tone: 'bg-mint text-[#478a70]' },
  ]
  return <><PageHeading eyebrow="Module 03 · Security Insights & Learning" title="Your security snapshot." description="A running summary of messages checked in this local ScamShield database." /><div className="grid gap-4 md:grid-cols-3">{metrics.map(({ label, value, foot, icon: Icon, tone }) => <div key={label} className="rounded-[20px] border border-line bg-card p-5 shadow-soft"><div className="flex items-center justify-between"><span className="text-[11px] font-semibold text-muted">{label}</span><span className={`rounded-xl p-2 ${tone}`}><Icon size={16} /></span></div><div className="mt-3 font-display text-[30px] font-extrabold tracking-tight">{value}</div><div className="mt-1 text-[10px] text-[#8a8d9d]">{foot}</div></div>)}</div><div className="mt-5 grid gap-5 xl:grid-cols-[1.35fr_1fr]"><section className="rounded-[22px] border border-line bg-card p-5 shadow-soft md:p-6"><div className="flex items-start justify-between"><div><h2 className="font-display text-[16px] font-extrabold">Recent scan history</h2><p className="mb-0 mt-1 text-[11px] text-muted">Saved locally in SQLite on this computer.</p></div><Clock3 size={18} className="text-violet" /></div>{history.length ? <div className="mt-3 divide-y divide-[#f0eee8]">{history.slice(0, 8).map((scan) => <div key={scan.id} className="flex items-center justify-between gap-4 py-3"><div className="min-w-0"><div className="truncate text-[12px] font-semibold text-[#444657]">{scan.message}</div><div className="mt-1 text-[10px] text-[#8a8d9d]">{new Date(scan.created_at).toLocaleString()} · {languageLabel(scan.language)}{scan.model_label && ` · Model: ${scan.model_label}`}</div></div><RiskPill risk={scan.risk} /></div>)}</div> : <div className="my-8 text-center text-[12px] text-[#8a8d9d]">Your scans will appear here after you check a message.</div>}</section><section className="rounded-[22px] border border-line bg-card p-5 shadow-soft md:p-6"><h2 className="font-display text-[16px] font-extrabold">Scan distribution</h2><p className="mb-5 mt-1 text-[11px] text-muted">Across all saved scans</p>{total ? <div className="space-y-4">{[['High risk', counts.high, '#c87979'], ['Medium risk', counts.medium, '#d6a16e'], ['Low risk', counts.low, '#70a58c']].map(([label, count, color]) => <div key={label}><div className="mb-1.5 flex justify-between text-[11px] text-[#66697a]"><span>{label}</span><span>{count} · {Math.round((count / total) * 100)}%</span></div><div className="h-2 overflow-hidden rounded-full bg-[#f0eee8]"><div className="h-full rounded-full" style={{ width: `${(count / total) * 100}%`, background: color }} /></div></div>)}</div> : <div className="py-4 text-[12px] text-[#8a8d9d]">Scan a message to start building your snapshot.</div>}<div className="mt-6 rounded-xl border border-[#dcebe4] bg-[#eaf3ef] p-3.5 text-[11px] leading-relaxed text-[#416a59]"><strong className="block text-[#35614e]">Your privacy</strong>Message text and results are stored locally in SQLite. Translation calls are sent to the provider only when its API is configured.</div></section></div><section className="mt-5 rounded-[20px] border border-[#e5e2f0] bg-[#f8f7fb] p-5 md:p-6"><div className="flex items-start gap-3"><div className="rounded-xl bg-white/80 p-2.5 text-violet"><HeartHandshake size={17} /></div><div className="flex-1"><h2 className="font-display text-[14px] font-extrabold">Was this result useful?</h2><p className="mb-3 mt-1 text-[11px] text-muted">Optional feedback helps the team review confusing or unexpected results.</p><div className="flex flex-wrap items-center gap-2">{[['yes', 'Yes'], ['somewhat', 'Somewhat'], ['no', 'No']].map(([value, label]) => <button key={value} onClick={() => setFeedback(value)} className={`rounded-lg border px-3 py-2 text-[11px] font-semibold transition ${feedback === value ? 'border-violet bg-violet text-white' : 'border-[#e3e0ec] bg-white/60 text-[#777b8e] hover:border-violet/40'}`}>{label}</button>)}<button disabled={!feedback || feedbackSent} onClick={saveFeedback} className="ml-0 flex items-center gap-1.5 rounded-lg px-3 py-2 text-[11px] font-bold text-violet disabled:opacity-40 sm:ml-1">{feedbackSent ? <><Check size={13} /> Saved</> : <>Save feedback <ArrowRight size={13} /></>}</button></div></div></div></section></>
}

function RiskPill({ risk }) {
  const styles = { High: 'bg-[#f8e9e9] text-[#aa5353]', Medium: 'bg-peach text-[#a36d36]', Low: 'bg-mint text-[#3e7b62]' }
  return <span className={`shrink-0 rounded-full px-2.5 py-1 text-[9px] font-extrabold ${styles[risk]}`}>{risk}</span>
}

function languageLabel(language) {
  return ({ auto: 'Auto-detect', en: 'English', hi: 'Hindi', mr: 'Marathi' })[language] || language
}

export default App
