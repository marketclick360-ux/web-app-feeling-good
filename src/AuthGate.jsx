import React, { useState, useEffect } from 'react'
import { supabase } from './supabaseClient'

export default function AuthGate({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
    })
    return () => listener.subscription.unsubscribe()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin }
    })
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

  if (session) return (
    <>
      <button className="sign-out-btn" onClick={handleSignOut}>Sign Out</button>
      {React.Children.map(children, child => React.cloneElement(child, { userId: session.user.id }))}
    </>
  )

  return (
    <div className="auth-gate">
      <div className="auth-card">
        <h1>Eat Pray Study</h1>
        <p className="auth-subtitle">Pioneer Spiritual Growth Tracker</p>
        <h2>Sign In</h2>
        <form onSubmit={handleSubmit}>
          <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required className="auth-input" />
          {error && <p className="auth-error">{error}</p>}
          {message && <p className="auth-message">{message}</p>}
          <button type="submit" className="auth-btn">Send Magic Link</button>
        </form>
        <p className="auth-hint">We'll email you a link to sign in — no password needed.</p>
      </div>
    </div>
  )
}
