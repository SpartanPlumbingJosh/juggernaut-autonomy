import { Metadata } from 'next';
import JTClient from './JTClient';

export const metadata: Metadata = {
  title: 'Spartan Job Tracker',
};

export default async function JobPage({ params }: { params: Promise<{ jobNumber: string }> }) {
  const { jobNumber } = await params;
  return <JTClient jobNumber={jobNumber} />;
}