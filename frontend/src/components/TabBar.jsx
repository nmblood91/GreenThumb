export function TabBar({ activeTab, onChange }) {
  const tabs = [
    { key: 'gantry', label: 'Gantry' },
    { key: 'general', label: 'General' },
    { key: 'plants', label: 'Plants' },
    { key: 'logs', label: 'Logs' },
  ]

  return (
    <nav className="tab-bar">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          className={activeTab === tab.key ? 'tab active' : 'tab'}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}
