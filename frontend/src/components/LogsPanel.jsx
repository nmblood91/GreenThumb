export function LogsPanel({ logs }) {
  const reversedLogs = logs.length ? [...logs].reverse() : []

  return (
    <section className="panel-section">
      <h2>Recent Logs</h2>
      <div className="log-box">
        {reversedLogs.length ? reversedLogs.join('') : 'No logs yet.'}
      </div>
    </section>
  )
}
