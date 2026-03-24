import { Metadata } from 'next';
import EfficiencyClient from './EfficiencyClient';

export const metadata: Metadata = {
  title: 'Install Efficiency — Spartan Job Tracker',
};

export default function AnalyticsPage() {
  return <EfficiencyClient />;
}
