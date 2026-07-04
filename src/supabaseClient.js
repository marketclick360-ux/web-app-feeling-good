import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// True only when both connection vars are present. Preview deployments that
// don't expose the Supabase env vars will be false, so the UI can guide the
// user to Guest mode instead of failing with a cryptic error.
export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey)

if (!isSupabaseConfigured && typeof console !== 'undefined') {
  console.warn('[supabase] Missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY — sign-in is disabled; Guest mode still works.')
}

// Fall back to harmless placeholders so createClient never throws at import
// time when config is absent (which would blank the whole app).
export const supabase = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabaseAnonKey || 'placeholder-anon-key',
  {
  auth: {
        flowType: 'pkce',
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    storageKey: 'eat-pray-study-auth',
    storage: window.localStorage
  }
})
