import React, { useState, useEffect } from 'react'
import { supabase } from './supabaseClient'

export default function AuthGate({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [guestMode, setGuestMode] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (session) {
        setGuestMode(false)
        setShowLogin(false)
      }
    })
    return () => listener.subscription.unsubscribe()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setSending(true)
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin }
    })
    setSending(false)
    if (error) setError(error.message)
    else setMessage('Check your email for a login link!')
  }

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    setSession(null)
  }

  if (loading) return (
    <div className="auth-loading">
      <div className="auth-spinner"></div>
      <p>Loading...</p>
    </div>
  )

  // Signed in user
  if (session) return (
    <>
      <button className="sign-out-btn" onClick={handleSignOut}>
        Sign Out
      </button>
      {React.Children.map(children, child =>
        React.cloneElement(child, { userId: session.user.id }))}
    </>
  )

  // Guest mode - show app with sign-in option
  if (guestMode && !showLogin) return (
    <>
      <button className="sign-in-btn" onClick={() => setShowLogin(true)}>Sign In</button>
      {React.Children.map(children, child =>
        React.cloneElement(child, { userId: null }))}
    </>
  )

  // Login screen (initial or triggered from guest mode)
  return (
    <div className="auth-gate">
      <div className="auth-card">
        <h1>Eat Pray Study</h1>
        <p className="auth-subtitle">Pioneer Spiritual Growth Tracker</p>
        <h2>Welcome Back</h2>
        <p className="auth-desc">Enter your email to sign in. New here? Same button — we'll create your account automatically.</p>
        <form onSubmit={handleSubmit}>
          <input type="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required className="auth-input" autoComplete="email" autoFocus />
          {error && <p className="auth-error">{error}</p>}
          {message && <p className="auth-message">{message}</p>}
          <button type="submit" className="auth-btn" disabled={sending}>
            {sending ? 'Sending...' : 'Send Magic Link'}
          </button>
        </form>
        <p className="auth-hint">We'll email you a secure link — no password needed. Once you tap it, you're signed in and your data syncs across all your devices. You stay logged in until you sign out.</p>
        <button className="guest-btn" onClick={() => { setGuestMode(true); setShowLogin(false) }}>Continue as Guest</button>
      </div>
    </div>
  )
}
