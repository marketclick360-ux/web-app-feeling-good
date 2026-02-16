import React, { useState, useEffect } from 'react'
import { supabase } from './supabaseClient'

export default function AuthGate({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSignUp, setIsSignUp] = useState(false)
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
    if (isSignUp) {
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) setError(error.message)
      else setMessage('Check your email for a confirmation link!')
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) setError(error.message)
    }
  }

  if (loading) return (
    <div className="auth-loading">
      <div className="auth-spinner"></div>
      <p>Loading...</p>
    </div>
  )

  if (session) return React.Children.map(children, child => React.cloneElement(child, { userId: session.user.id }))

  return (
    <div className="auth-gate">
      <div className="auth-card">
        <h1 className="auth-title">Eat Pray Study</h1>
        <p className="auth-subtitle">Pioneer Spiritual Growth Tracker</p>
        <h2 className="auth-heading">{isSignUp ? 'Create Account' : 'Sign In'}</h2>
        <form onSubmit={handleSubmit} className="auth-form">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="auth-input"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            minLength={6}
            className="auth-input"
          />
          {error && <p className="auth-error">{error}</p>}
          {message && <p className="auth-message">{message}</p>}
          <button type="submit" className="auth-btn">
            {isSignUp ? 'Sign Up' : 'Sign In'}
          </button>
        </form>
        <p
          className="auth-toggle"
          onClick={() => { setIsSignUp(!isSignUp); setError(''); setMessage('') }}
        >
          {isSignUp ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
        </p>
      </div>
    </div>
  )
}
