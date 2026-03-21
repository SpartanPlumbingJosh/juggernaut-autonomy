import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

const SLACK_CLIENT_ID = process.env.SLACK_CLIENT_ID || '';
const SLACK_CLIENT_SECRET = process.env.SLACK_CLIENT_SECRET || '';
const REDIRECT_URI = process.env.NEXT_PUBLIC_SITE_URL
  ? `${process.env.NEXT_PUBLIC_SITE_URL}/api/auth/slack/callback`
  : 'https://jt.spartan-plumbing.com/api/auth/slack/callback';

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get('code');
  const state = request.nextUrl.searchParams.get('state') || '/';
  const error = request.nextUrl.searchParams.get('error');

  if (error || !code) {
    return NextResponse.redirect(new URL('/?auth_error=denied', request.url));
  }

  try {
    // Exchange code for user identity
    const tokenRes = await fetch('https://slack.com/api/oauth.v2.access', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id: SLACK_CLIENT_ID,
        client_secret: SLACK_CLIENT_SECRET,
        code,
        redirect_uri: REDIRECT_URI,
      }),
    });
    const tokenData = await tokenRes.json();

    if (!tokenData.ok || !tokenData.authed_user) {
      console.error('Slack OAuth error:', tokenData);
      return NextResponse.redirect(new URL('/?auth_error=slack_failed', request.url));
    }

    // Get user identity using the user token
    const identityRes = await fetch('https://slack.com/api/users.identity', {
      headers: { 'Authorization': `Bearer ${tokenData.authed_user.access_token}` },
    });
    const identity = await identityRes.json();

    if (!identity.ok) {
      console.error('Slack identity error:', identity);
      return NextResponse.redirect(new URL('/?auth_error=identity_failed', request.url));
    }

    const user = {
      slack_user_id: identity.user.id,
      name: identity.user.name,
      email: identity.user.email || '',
      avatar: identity.user.image_192 || identity.user.image_72 || '',
    };

    // Upsert user preferences (create record if first login)
    const safeName = user.name.replace(/'/g, "''");
    await query(`
      INSERT INTO spartan_ops.user_preferences (user_name, slack_member_id, theme, updated_at)
      VALUES ('${safeName}', '${user.slack_user_id}', 'dark', now())
      ON CONFLICT (user_name) DO UPDATE SET slack_member_id = '${user.slack_user_id}', updated_at = now()
    `).catch(() => {});

    // Load their saved theme
    const prefRows = await query(`
      SELECT theme FROM spartan_ops.user_preferences WHERE user_name = '${safeName}' LIMIT 1
    `).catch(() => []);
    const savedTheme = (prefRows as any[])?.[0]?.theme || 'dark';

    // Set auth cookie with user info — redirect back to the page they came from
    const userData = JSON.stringify({ ...user, theme: savedTheme });
    const response = NextResponse.redirect(new URL(state, request.url));
    response.cookies.set('jt_user', userData, {
      httpOnly: false,
      secure: true,
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 365,
      path: '/',
    });

    return response;
  } catch (err) {
    console.error('OAuth callback error:', err);
    return NextResponse.redirect(new URL('/?auth_error=server_error', request.url));
  }
}
