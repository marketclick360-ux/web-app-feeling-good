import React, { useState, useEffect, useRef } from 'react'
import { supabase } from './supabaseClient'
const COOLDOWN_SECONDS = 60
export default function AuthGate({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [email, setEmail] = useState('')
  const [otpToken, setOtpToken] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [guestMode, setGuestMode] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const [sending, setSending] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [step, setStep] = useState('email')
  const [cooldown, setCooldown] = useState(0)
  const cooldownRef = useRef(null)
  const otpInputRef = useRef(null)

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data }) => {
      if (data.session) {
        const { data: refreshed, error: refreshErr } = await supabase.auth.refreshSession()
        if (refreshErr || !refreshed.session) {
          console.warn('Session expired, clearing stale session')
          await supabase.auth.signOut()
          setSession(null)
        } else {
          setSession(refreshed.session)
        }
      } else {
        setSession(null)
      }
      setLoading(false)
    })
    const { data: listener } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'TOKEN_REFRESHED' && !session) {
        console.warn('Token refresh failed, signing out')
        setSession(null)
      } else if (event === 'SIGNED_OUT') {
        setSession(null)
      } else {
        setSession(session)
        if (session) {
          setGuestMode(false)
          setShowLogin(false)
        }
      }
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
      setCooldown(prev => {
        if (prev <= 1) {
          clearInterval(cooldownRef.current)
          cooldownRef.current = null
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  const handleSendCode = async (e) => {
    e.preventDefault()
    if (cooldown > 0) return
    setError('')
    setMessage('')
    setSending(true)
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { shouldCreateUser: true }
    })
    setSending(false)
    if (error) {
      if (error.message.toLowerCase().includes('rate') || error.status === 429) {
        setError('Too many requests. Please wait a moment before trying again.')
        startCooldown()
      } else {
        setError(error.message)
      }
    } else {
      setMessage('Code sent! Check your email.')
      setStep('otp')
      startCooldown()
      setTimeout(() => otpInputRef.current?.focus(), 100)
    }
  }

  const handleVerifyCode = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setVerifying(true)
    const { error } = await supabase.auth.verifyOtp({
            email: email.trim(),
      token: otpToken,
      type: 'email'
    })
    setVerifying(false)
    if (error) {
      if (error.message.toLowerCase().includes('expired')) {
        setError('Code expired. Please request a new one.')
      } else if (error.message.toLowerCase().includes('invalid')) {
        setError('Invalid code. Please check and try again.')
      } else {
        setError(error.message)
      }
    }
  }

  const handleResendCode = async () => {
    if (cooldown > 0) return
    setError('')
    setMessage('')
    setSending(true)
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { shouldCreateUser: true }
    })
    setSending(false)
    if (error) {
      if (error.message.toLowerCase().includes('rate') || error.status === 429) {
        setError('Too many requests. Please wait before trying again.')
      } else {
        setError(error.message)
      }
    } else {
      setMessage('New code sent!')
    }
    startCooldown()
  }

  const handleBackToEmail = () => {
    setStep('email')
    setOtpToken('')
    setError('')
    setMessage('')
  }

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    setSession(null)
    setStep('email')
    setOtpToken('')
    setEmail('')
  }

  if (loading) return (
    <div className="auth-wrapper">
      <p className="auth-loading">Loading...</p>
    </div>
  )

  if (session) return (
    <>
      {React.Children.map(children, child =>
        React.cloneElement(child, { userId: session.user.id, onSignOut: handleSignOut }))}
    </>
  )

  if (guestMode && !showLogin) return (
    <>
      {React.Children.map(children, child =>
        React.cloneElement(child, { userId: null, onSignOut: null, onSignIn: () => setShowLogin(true) }))}
    </>
  )

  if (step === 'email') return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <h1 className="auth-title">Eat Pray Study</h1>
        <p className="auth-subtitle">Pioneer Spiritual Growth Tracker</p>
        <h2 className="auth-heading">Welcome Back</h2>
        <p className="auth-text">Enter your email to sign in. New here? Same button \u2014 we'll create your account automatically.</p>
        <form onSubmit={handleSendCode}>
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="auth-input"
            autoComplete="email"
            autoFocus
          />
          {error && <p className="auth-error">{error}</p>}
          {message && <p className="auth-success">{message}</p>}
          <button type="submit" className="auth-btn" disabled={sending || cooldown > 0}>
            {sending ? 'Sending...' : cooldown > 0 ? `Resend in ${cooldown}s` : 'Send Code'}
          </button>
        </form>
        <p className="auth-hint">We'll email you a secure code \u2014 no password needed. You stay signed in until you sign out.</p>
        <button className="guest-btn" onClick={() => { setGuestMode(true); setShowLogin(false) }}>
          Continue as Guest
        </button>
      </div>
    </div>
  )

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <h1 className="auth-title">Eat Pray Study</h1>
        <p className="auth-subtitle">Pioneer Spiritual Growth Tracker</p>
        <h2 className="auth-heading">Enter Your Code</h2>
        <p className="auth-text">We sent a code to <strong>{email}</strong></p>
        <form onSubmit={handleVerifyCode}>
          <input
            ref={otpInputRef}
            type="text"
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            placeholder="000000"
            value={otpToken}
            onChange={e => setOtpToken(e.target.value.replace(/\D/g, '').slice(0, 6))}
            required
            className="auth-input"
            autoComplete="one-time-code"
            autoFocus
            style={{ textAlign: 'center', letterSpacing: '6px', fontSize: '1.4rem', fontFamily: 'monospace' }}
          />
          {error && <p className="auth-error">{error}</p>}
          {message && <p className="auth-success">{message}</p>}
          <button type="submit" className="auth-btn" disabled={verifying || otpToken.length < 6}>
            {verifying ? 'Verifying...' : 'Verify'}
          </button>
        </form>
        <p className="auth-hint">Didn't get it? Check your spam folder.</p>
        <button className="guest-btn" onClick={handleResendCode} disabled={cooldown > 0} style={{ marginBottom: '8px' }}>
          {cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend Code'}
        </button>
        <button className="guest-btn" onClick={handleBackToEmail}>\u2190 Use a different email</button>
      </div>
    </div>
  )
}
