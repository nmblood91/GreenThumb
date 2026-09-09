export function LogsPanel({ logs }) {
  return (
    <section className="panel-section">
      <h2>Recent Logs</h2>
      <div className="log-box">
        {logs.length ? logs.join('') : 'No logs yet.'}
      </div>
    </section>
  )
}
