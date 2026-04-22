import { createClient } from '@supabase/supabase-js';

export default async function handler(req, res) {
  try {
    const supabase = createClient(
      process.env.VITE_SUPABASE_URL,
      process.env.SUPABASE_SERVICE_ROLE_KEY
    );

    // Simple ping: fetch 1 row from auth.users to keep the project alive
    const { error } = await supabase.auth.admin.listUsers({ page: 1, perPage: 1 });

    if (error) {
      console.error('Keep-alive ping error:', error.message);
      return res.status(500).json({ ok: false, error: error.message });
    }

    console.log('Keep-alive ping succeeded at', new Date().toISOString());
    return res.status(200).json({ ok: true, pingedAt: new Date().toISOString() });
  } catch (err) {
    console.error('Keep-alive unexpected error:', err);
    return res.status(500).json({ ok: false, error: err.message });
  }
}
