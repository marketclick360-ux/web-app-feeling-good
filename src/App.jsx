import { useState } from 'react'

function App() {
  const [mood, setMood] = useState('great')

  return (
    <div className="app">
      <header className="hero">
        <h1>Feeling Good</h1>
        <p>Your wellness companion app</p>
      </header>

      <main className="content">
        <section className="mood-card">
          <h2>How are you feeling today?</h2>
          <div className="mood-buttons">
            <button onClick={() => setMood('great')} className={mood === 'great' ? 'active' : ''}>Great</button>
            <button onClick={() => setMood('good')} className={mood === 'good' ? 'active' : ''}>Good</button>
            <button onClick={() => setMood('okay')} className={mood === 'okay' ? 'active' : ''}>Okay</button>
            <button onClick={() => setMood('low')} className={mood === 'low' ? 'active' : ''}>Low</button>
          </div>
          <p className="mood-message">
            {mood === 'great' && 'Awesome! Keep that energy going!'}
            {mood === 'good' && 'Nice! Glad you are doing well.'}
            {mood === 'okay' && 'Hang in there. Better days ahead!'}
            {mood === 'low' && 'Take it easy. You are not alone.'}
          </p>
        </section>

        <section className="features">
          <div className="feature-card">
            <h3>Track Your Mood</h3>
            <p>Log how you feel every day and see your progress.</p>
          </div>
          <div className="feature-card">
            <h3>Daily Tips</h3>
            <p>Get personalized wellness tips to boost your day.</p>
          </div>
          <div className="feature-card">
            <h3>Community</h3>
            <p>Connect with others on their wellness journey.</p>
          </div>
        </section>
      </main>

      <footer className="footer">
        <p>Feeling Good App &copy; 2026 | Built with React + Vite</p>
      </footer>
    </div>
  )
}

export default App
