export default function Home() {
  return (
    <div className="min-h-screen bg-surface-0 flex items-center justify-center">
      <div className="text-center max-w-md">
        <div className="w-14 h-14 rounded-2xl bg-spartan-600 flex items-center justify-center font-display font-bold text-xl text-white mx-auto mb-4">
          JT
        </div>
        <h1 className="text-2xl font-display font-bold text-white mb-2">Spartan Job Tracker</h1>
        <p className="text-sm text-slate-400 mb-6">
          Access a job tracker via its direct link from your Slack channel bookmark.
        </p>
        <p className="text-xs text-slate-600">
          Spartan Plumbing LLC · Dayton, OH
        </p>
      </div>
    </div>
  );
}