import React, { useState, useEffect, useRef } from 'react'
import { supabase } from './supabaseClient'

const COOLDOWN_SECONDS = 60

export default function AuthGate({ children }) {
  const [session, setSession]       = useState(null)
  const [loading, setLoading]       = useState(true)
  const [email, setEmail]           = useState('')
  const [otpToken, setOtpToken]     = useState('')
  const [error, setError]           = useState('')
  const [message, setMessage]       = useState('')
  const [guestMode, setGuestMode]   = useState(false)
  const [showLogin, setShowLogin]   = useState(false)
  const [sending, setSending]       = useState(false)
  const [verifying, setVerifying]   = useState(false)
  const [step, setStep]             = useState('email')
  const [cooldown, setCooldown]     = useState(0)
  const cooldownRef  = useRef(null)
  const otpInputRef  = useRef(null)

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data }) => {
      if (data.session) {
        const { data: refreshed, error: refreshErr } = await supabase.auth.refreshSession()
        if (refreshErr || !refreshed.session) { await supabase.auth.signOut(); setSession(null) }
        else setSession(refreshed.session)
      } else { setSession(null) }
      setLoading(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'TOKEN_REFRESHED' && !session) setSession(null)
      else if (event === 'SIGNED_OUT') setSession(null)
      else { setSession(session); if (session) { setGuestMode(false); setShowLogin(false) } }
    })

    return () => {
      listener.subscription.unsubscribe()
      if (cooldownRef.current) clearInterval(cooldownRef.current)
    }
  }, [])

  const startCooldown = () => {
    setCooldown(COOLDOWN_SECONDS)
    if (cooldownRef.current) clearInterval(cooldownRef.current)
    cooldownRef.current = setInterval(() => {
      setCooldown(p => { if (p <= 1) { clearInterval(cooldownRef.current); cooldownRef.current = null; return 0 } return p - 1 })
    }, 1000)
  }

  const handleSendCode = async (e) => {
    e.preventDefault()
    if (cooldown > 0) return
    setError(''); setMessage(''); setSending(true)
    const { error } = await supabase.auth.signInWithOtp({ email, options: { shouldCreateUser: true } })
    setSending(false)
    if (error) {
      setError(error.status === 429 ? 'Too many requests. Please wait a moment.' : error.message)
      if (error.status === 429) startCooldown()
    } else {
      setMessage('Code sent! Check your email.'); setStep('otp'); startCooldown()
      setTimeout(() => otpInputRef.current?.focus(), 100)
    }
  }

  const handleVerifyCode = async (e) => {
    e.preventDefault()
    setError(''); setMessage(''); setVerifying(true)
    const { error } = await supabase.auth.verifyOtp({ email, token: otpToken, type: 'email' })
    setVerifying(false)
    if (error) setError(error.message.includes('expired') ? 'Code expired. Request a new one.' : error.message.includes('invalid') ? 'Invalid code. Please try again.' : error.message)
  }

  const handleResendCode = async () => {
    if (cooldown > 0) return
    setError(''); setMessage(''); setSending(true)
    const { error } = await supabase.auth.signInWithOtp({ email, options: { shouldCreateUser: true } })
    setSending(false)
    if (error) setError(error.message)
    else setMessage('New code sent!')
    startCooldown()
  }

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    setSession(null); setStep('email'); setOtpToken(''); setEmail('')
  }

  if (loading) return (
    <div className="auth-loading">
      <div className="auth-spinner" />
      <p>Loading…</p>
    </div>
  )

  if (session) return (
    <>
      <button className="sign-out-btn" onClick={handleSignOut}>Sign Out</button>
      {React.Children.map(children, child => React.cloneElement(child, { userId: session.user.id }))}
    </>
  )

  if (guestMode && !showLogin) return (
    <>
      <button className="sign-in-btn" onClick={() => setShowLogin(true)}>Sign In</button>
      {React.Children.map(children, child => React.cloneElement(child, { userId: null }))}
    </>
  )

  if (step === 'email') return (
    <div className="auth-gate">
      <div className="auth-card">
        <h1>Eat Pray Study</h1>
        <p className="auth-subtitle">Pioneer Spiritual Growth Tracker</p>
        <h2>Welcome Back</h2>
        <p className="auth-desc">Enter your email to sign in. New? Same button — we'll create your account automatically.</p>
        <form onSubmit={handleSendCode}>
          <input type="email" className="auth-input" placeholder="you@example.com" value={email}
            onChange={e => setEmail(e.target.value)} required autoComplete="email" autoFocus />
          {error   && <p className="auth-error">{error}</p>}
          {message && <p className="auth-message">{message}</p>}
          <button type="submit" className="auth-btn" disabled={sending || cooldown > 0}>
            {sending ? 'Sending…' : cooldown > 0 ? `Resend in ${cooldown}s` : 'Send Code'}
          </button>
        </form>
        <p className="auth-hint">We'll email you a secure code — no password needed.</p>
        <div className="auth-divider">or</div>
        <button className="guest-btn" onClick={() => { setGuestMode(true); setShowLogin(false) }}>
          Continue as Guest
        </button>
      </div>
    </div>
  )

  return (
    <div className="auth-gate">
      <div className="auth-card">
        <h1>Eat Pray Study</h1>
        <p className="auth-subtitle">Pioneer Spiritual Growth Tracker</p>
        <h2>Enter Your Code</h2>
        <p className="auth-desc">We sent a 6-digit code to <strong>{email}</strong></p>
        <form onSubmit={handleVerifyCode}>
          <input ref={otpInputRef} type="text" className="auth-input" inputMode="numeric"
            pattern="[0-9]{6}" maxLength={6} placeholder="000000" value={otpToken}
            onChange={e => setOtpToken(e.target.value.replace(/\D/g,'').slice(0,6))}
            required autoComplete="one-time-code" autoFocus
            style={{textAlign:'center', letterSpacing:'8px', fontSize:'1.4rem', fontFamily:'DM Mono, monospace'}} />
          {error   && <p className="auth-error">{error}</p>}
          {message && <p className="auth-message">{message}</p>}
          <button type="submit" className="auth-btn" disabled={verifying}>
            {verifying ? 'Verifying…' : 'Verify'}
          </button>
        </form>
        <p className="auth-hint">Didn't get it? Check your spam folder.</p>
        <div style={{display:'flex', gap:'8px', marginTop:'0.5rem'}}>
          <button className="guest-btn" onClick={handleResendCode} disabled={cooldown > 0} style={{flex:1}}>
            {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend Code'}
          </button>
          <button className="guest-btn" onClick={() => { setStep('email'); setOtpToken(''); setError(''); setMessage('') }} style={{flex:1}}>
            ← Change Email
          </button>
        </div>
      </div>
    </div>
  )
}
