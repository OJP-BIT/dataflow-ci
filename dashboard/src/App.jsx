import { useState, useEffect } from "react"
import axios from "axios"

const API_URL = "http://localhost:8000"

function StatusBadge({ status }) {
  const colors = {
    passed: "bg-green-500",
    failed: "bg-red-500",
    pending: "bg-yellow-500",
    assigned: "bg-blue-500",
    running: "bg-blue-400",
    reassigned: "bg-orange-500",
  }
  return (
    <span className={`${colors[status] || "bg-gray-500"} text-white text-xs font-bold px-2 py-1 rounded-full uppercase`}>
      {status}
    </span>
  )
}

function CheckRow({ check }) {
  return (
    <div className={`flex items-start gap-3 p-2 rounded text-sm ${check.passed ? "bg-green-950" : "bg-red-950"}`}>
      <span className="mt-0.5">{check.passed ? "✅" : "❌"}</span>
      <div>
        <div className="font-mono text-xs text-gray-300">{check.check}</div>
        <div className="text-gray-400 text-xs">{check.file} · {check.category}</div>
        <div className={check.passed ? "text-green-400 text-xs" : "text-red-400 text-xs"}>{check.message}</div>
      </div>
    </div>
  )
}

function JobCard({ job, selected, onClick }) {
  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-lg border cursor-pointer transition-all ${
        selected
          ? "border-blue-500 bg-gray-800"
          : "border-gray-700 bg-gray-900 hover:border-gray-500"
      }`}
    >
      <div className="flex justify-between items-start mb-2">
        <StatusBadge status={job.status} />
        <span className="text-gray-500 text-xs">
          {new Date(job.created_at).toLocaleTimeString()}
        </span>
      </div>
      <div className="font-mono text-sm text-white mt-2">
        {job.commit_id.slice(0, 12)}
      </div>
      <div className="text-gray-500 text-xs mt-1">
        {job.assigned_runner || "unassigned"}
      </div>
    </div>
  )
}

function JobDetail({ job }) {
  if (!job) return (
    <div className="flex items-center justify-center h-full text-gray-600">
      Select a job to see details
    </div>
  )

  const results = job.results || []
  const structural = results.filter(r => r.category === "structural")
  const statistical = results.filter(r => r.category === "statistical")
  const referential = results.filter(r => r.category === "referential")
  const passed = results.filter(r => r.passed).length
  const failed = results.filter(r => !r.passed).length

  return (
    <div className="h-full overflow-y-auto">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <StatusBadge status={job.status} />
          <span className="font-mono text-white">{job.commit_id}</span>
        </div>
        <div className="text-gray-400 text-sm">
          Runner: {job.assigned_runner || "unassigned"} ·
          Duration: {job.duration_seconds ? `${job.duration_seconds}s` : "—"} ·
          Checks: <span className="text-green-400">{passed} passed</span> / <span className="text-red-400">{failed} failed</span>
        </div>
      </div>

      {[
        { label: "Structural", items: structural },
        { label: "Statistical", items: statistical },
        { label: "Referential", items: referential },
      ].map(({ label, items }) => (
        <div key={label} className="mb-6">
          <h3 className="text-gray-300 font-semibold mb-2 text-sm uppercase tracking-wider">
            {label} ({items.filter(r => r.passed).length}/{items.length} passed)
          </h3>
          <div className="flex flex-col gap-1">
            {items.length === 0
              ? <div className="text-gray-600 text-sm">No checks</div>
              : items.map((c, i) => <CheckRow key={i} check={c} />)
            }
          </div>
        </div>
      ))}
    </div>
  )
}

function RunnerHealth({ runners }) {
  return (
    <div className="flex gap-3 mb-6">
      {runners.map(r => (
        <div key={r} className="flex items-center gap-2 bg-gray-800 px-3 py-2 rounded-lg border border-gray-700">
          <div className="w-2 h-2 rounded-full bg-green-400"></div>
          <span className="text-gray-300 text-sm">{r}</span>
        </div>
      ))}
    </div>
  )
}

export default function App() {
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)
  const [health, setHealth] = useState(null)

  const fetchJobs = async () => {
    try {
      const res = await axios.get(`${API_URL}/jobs`)
      setJobs(res.data)
      if (selectedJob) {
        const updated = res.data.find(j => j.job_id === selectedJob.job_id)
        if (updated) setSelectedJob(updated)
      }
    } catch (e) {
      console.error("Could not fetch jobs", e)
    }
  }

  const fetchHealth = async () => {
    try {
      const res = await axios.get(`${API_URL}/health`)
      setHealth(res.data)
    } catch (e) {
      console.error("Could not fetch health", e)
    }
  }

  useEffect(() => {
    fetchJobs()
    fetchHealth()
    const interval = setInterval(() => {
      fetchJobs()
      fetchHealth()
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold">DataFlow CI</h1>
            <p className="text-gray-500 text-sm">Pipeline validation dashboard</p>
          </div>
          {health && (
            <div className="flex gap-6 text-sm">
              <div className="text-center">
                <div className="text-white font-bold">{health.active_runners}</div>
                <div className="text-gray-500">runners</div>
              </div>
              <div className="text-center">
                <div className="text-white font-bold">{health.pending_jobs}</div>
                <div className="text-gray-500">pending</div>
              </div>
              <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold ${
                health.status === "ok" ? "bg-green-900 text-green-400" : "bg-red-900 text-red-400"
              }`}>
                <div className="w-2 h-2 rounded-full bg-current"></div>
                {health.status.toUpperCase()}
              </div>
            </div>
          )}
        </div>
      </header>

      <div className="flex h-[calc(100vh-73px)]">
        <div className="w-80 border-r border-gray-800 p-4 overflow-y-auto">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
              Jobs ({jobs.length})
            </h2>
            <button
              onClick={fetchJobs}
              className="text-gray-500 hover:text-white text-xs"
            >
              Refresh
            </button>
          </div>
          <div className="flex flex-col gap-2">
            {jobs.map(job => (
              <JobCard
                key={job.job_id}
                job={job}
                selected={selectedJob?.job_id === job.job_id}
                onClick={() => setSelectedJob(job)}
              />
            ))}
          </div>
        </div>

        <div className="flex-1 p-6">
          <JobDetail job={selectedJob} />
        </div>
      </div>
    </div>
  )
}