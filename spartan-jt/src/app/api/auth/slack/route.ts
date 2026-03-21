import { NextResponse } from 'next/server';

const SLACK_CLIENT_ID = process.env.SLACK_CLIENT_ID || '';
const REDIRECT_URI = process.env.NEXT_PUBLIC_SITE_URL
  ? `${process.env.NEXT_PUBLIC_SITE_URL}/api/auth/slack/callback`
  : 'https://jt.spartan-plumbing.com/api/auth/slack/callback';

export async function GET(request: Request) {
  if (!SLACK_CLIENT_ID) {
    return NextResponse.json({ error: 'SLACK_CLIENT_ID not configured' }, { status: 500 });
  }
  const { searchParams } = new URL(request.url);
  const state = searchParams.get('state') || '/';
  const url = `https://slack.com/oauth/v2/authorize?client_id=${SLACK_CLIENT_ID}&user_scope=identity.basic,identity.email,identity.avatar&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&state=${encodeURIComponent(state)}`;
  return NextResponse.redirect(url);
}
