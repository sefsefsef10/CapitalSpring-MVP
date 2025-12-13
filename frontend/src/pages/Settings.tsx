import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Settings as SettingsIcon,
  Save,
  RefreshCw,
  FileText,
  Shield,
  Bell,
  Database,
  Zap,
} from 'lucide-react'
import clsx from 'clsx'

interface ProcessorConfig {
  confidence_threshold: number
  fallback_to_claude: boolean
  max_retries: number
}

interface ValidationConfig {
  strict_mode: boolean
  required_fields_only: boolean
  auto_create_exceptions: boolean
}

interface NotificationConfig {
  email_on_exception: boolean
  email_on_batch_complete: boolean
  slack_webhook_url: string
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState('processing')

  // Processing settings
  const [processorConfig, setProcessorConfig] = useState<ProcessorConfig>({
    confidence_threshold: 0.85,
    fallback_to_claude: true,
    max_retries: 3,
  })

  // Validation settings
  const [validationConfig, setValidationConfig] = useState<ValidationConfig>({
    strict_mode: true,
    required_fields_only: false,
    auto_create_exceptions: true,
  })

  // Notification settings
  const [notificationConfig, setNotificationConfig] = useState<NotificationConfig>({
    email_on_exception: true,
    email_on_batch_complete: false,
    slack_webhook_url: '',
  })

  const [isSaving, setIsSaving] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)
    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000))
    setIsSaving(false)
    toast.success('Settings saved successfully')
  }

  const tabs = [
    { id: 'processing', label: 'Processing', icon: Zap },
    { id: 'validation', label: 'Validation', icon: Shield },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'documents', label: 'Document Types', icon: FileText },
    { id: 'database', label: 'Database', icon: Database },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-500">Configure system preferences and processing rules</p>
        </div>
        <button onClick={handleSave} disabled={isSaving} className="btn-primary">
          {isSaving ? (
            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Save className="w-4 h-4 mr-2" />
          )}
          {isSaving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-56 flex-shrink-0">
          <nav className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={clsx(
                  'w-full flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-lg transition-colors',
                  activeTab === tab.id
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-100'
                )}
              >
                <tab.icon className="w-5 h-5" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          {activeTab === 'processing' && (
            <div className="card p-6 space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Processing Settings</h2>
              <p className="text-sm text-gray-500">
                Configure how documents are processed and extracted.
              </p>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Confidence Threshold
                  </label>
                  <p className="text-sm text-gray-500 mb-2">
                    Documents with confidence below this threshold will be flagged for review.
                  </p>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min="0.5"
                      max="0.99"
                      step="0.01"
                      value={processorConfig.confidence_threshold}
                      onChange={(e) =>
                        setProcessorConfig({
                          ...processorConfig,
                          confidence_threshold: parseFloat(e.target.value),
                        })
                      }
                      className="flex-1"
                    />
                    <span className="text-lg font-semibold text-gray-900 w-16 text-right">
                      {(processorConfig.confidence_threshold * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between py-4 border-t">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Claude AI Fallback
                    </label>
                    <p className="text-sm text-gray-500">
                      Use Claude AI when Document AI confidence is low or document type is unknown.
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      setProcessorConfig({
                        ...processorConfig,
                        fallback_to_claude: !processorConfig.fallback_to_claude,
                      })
                    }
                    className={clsx(
                      'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                      processorConfig.fallback_to_claude ? 'bg-primary-600' : 'bg-gray-200'
                    )}
                  >
                    <span
                      className={clsx(
                        'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                        processorConfig.fallback_to_claude ? 'translate-x-5' : 'translate-x-0'
                      )}
                    />
                  </button>
                </div>

                <div className="py-4 border-t">
                  <label className="block text-sm font-medium text-gray-700">
                    Maximum Retries
                  </label>
                  <p className="text-sm text-gray-500 mb-2">
                    Number of times to retry processing on failure.
                  </p>
                  <select
                    value={processorConfig.max_retries}
                    onChange={(e) =>
                      setProcessorConfig({
                        ...processorConfig,
                        max_retries: parseInt(e.target.value),
                      })
                    }
                    className="input max-w-xs"
                  >
                    <option value={1}>1 retry</option>
                    <option value={2}>2 retries</option>
                    <option value={3}>3 retries</option>
                    <option value={5}>5 retries</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'validation' && (
            <div className="card p-6 space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Validation Settings</h2>
              <p className="text-sm text-gray-500">
                Configure data validation rules and exception handling.
              </p>

              <div className="space-y-4">
                <div className="flex items-center justify-between py-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Strict Mode
                    </label>
                    <p className="text-sm text-gray-500">
                      Fail validation if any rule is violated. Otherwise, create warnings.
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      setValidationConfig({
                        ...validationConfig,
                        strict_mode: !validationConfig.strict_mode,
                      })
                    }
                    className={clsx(
                      'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                      validationConfig.strict_mode ? 'bg-primary-600' : 'bg-gray-200'
                    )}
                  >
                    <span
                      className={clsx(
                        'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                        validationConfig.strict_mode ? 'translate-x-5' : 'translate-x-0'
                      )}
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between py-4 border-t">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Required Fields Only
                    </label>
                    <p className="text-sm text-gray-500">
                      Only validate required fields, ignore optional field rules.
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      setValidationConfig({
                        ...validationConfig,
                        required_fields_only: !validationConfig.required_fields_only,
                      })
                    }
                    className={clsx(
                      'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                      validationConfig.required_fields_only ? 'bg-primary-600' : 'bg-gray-200'
                    )}
                  >
                    <span
                      className={clsx(
                        'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                        validationConfig.required_fields_only ? 'translate-x-5' : 'translate-x-0'
                      )}
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between py-4 border-t">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Auto-Create Exceptions
                    </label>
                    <p className="text-sm text-gray-500">
                      Automatically create exception records for validation failures.
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      setValidationConfig({
                        ...validationConfig,
                        auto_create_exceptions: !validationConfig.auto_create_exceptions,
                      })
                    }
                    className={clsx(
                      'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                      validationConfig.auto_create_exceptions ? 'bg-primary-600' : 'bg-gray-200'
                    )}
                  >
                    <span
                      className={clsx(
                        'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                        validationConfig.auto_create_exceptions ? 'translate-x-5' : 'translate-x-0'
                      )}
                    />
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="card p-6 space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Notification Settings</h2>
              <p className="text-sm text-gray-500">
                Configure email and Slack notifications.
              </p>

              <div className="space-y-4">
                <div className="flex items-center justify-between py-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Email on Exception
                    </label>
                    <p className="text-sm text-gray-500">
                      Send email notification when a critical exception is created.
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      setNotificationConfig({
                        ...notificationConfig,
                        email_on_exception: !notificationConfig.email_on_exception,
                      })
                    }
                    className={clsx(
                      'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                      notificationConfig.email_on_exception ? 'bg-primary-600' : 'bg-gray-200'
                    )}
                  >
                    <span
                      className={clsx(
                        'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                        notificationConfig.email_on_exception ? 'translate-x-5' : 'translate-x-0'
                      )}
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between py-4 border-t">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Email on Batch Complete
                    </label>
                    <p className="text-sm text-gray-500">
                      Send summary email when a batch of documents finishes processing.
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      setNotificationConfig({
                        ...notificationConfig,
                        email_on_batch_complete: !notificationConfig.email_on_batch_complete,
                      })
                    }
                    className={clsx(
                      'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                      notificationConfig.email_on_batch_complete ? 'bg-primary-600' : 'bg-gray-200'
                    )}
                  >
                    <span
                      className={clsx(
                        'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                        notificationConfig.email_on_batch_complete ? 'translate-x-5' : 'translate-x-0'
                      )}
                    />
                  </button>
                </div>

                <div className="py-4 border-t">
                  <label className="block text-sm font-medium text-gray-700">
                    Slack Webhook URL
                  </label>
                  <p className="text-sm text-gray-500 mb-2">
                    Optional: Send notifications to a Slack channel.
                  </p>
                  <input
                    type="url"
                    value={notificationConfig.slack_webhook_url}
                    onChange={(e) =>
                      setNotificationConfig({
                        ...notificationConfig,
                        slack_webhook_url: e.target.value,
                      })
                    }
                    className="input"
                    placeholder="https://hooks.slack.com/services/..."
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'documents' && (
            <div className="card p-6 space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Document Type Configuration</h2>
              <p className="text-sm text-gray-500">
                View supported document types and their processing rules.
              </p>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Document Type
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Primary Processor
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Fallback
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {[
                      { type: 'Portfolio Financials', processor: 'Document AI Form', fallback: 'Claude', status: 'Active' },
                      { type: 'Covenant Compliance', processor: 'Document AI Form', fallback: 'Claude', status: 'Active' },
                      { type: 'Borrowing Base', processor: 'Document AI Form', fallback: 'Claude', status: 'Active' },
                      { type: 'Capital Call', processor: 'Document AI Invoice', fallback: 'Claude', status: 'Active' },
                      { type: 'Distribution Notice', processor: 'Document AI Invoice', fallback: 'Claude', status: 'Active' },
                      { type: 'NAV Statement', processor: 'Document AI Form', fallback: 'Claude', status: 'Active' },
                      { type: 'AR Aging', processor: 'Document AI Form', fallback: 'OCR', status: 'Active' },
                      { type: 'Bank Statement', processor: 'Document AI Form', fallback: 'OCR', status: 'Active' },
                      { type: 'Invoice', processor: 'Document AI Invoice', fallback: 'Form Parser', status: 'Active' },
                      { type: 'Insurance Certificate', processor: 'Document AI Invoice', fallback: 'Claude', status: 'Active' },
                    ].map((doc, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{doc.type}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{doc.processor}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{doc.fallback}</td>
                        <td className="px-4 py-3">
                          <span className="badge badge-success">{doc.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'database' && (
            <div className="card p-6 space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Database Information</h2>
              <p className="text-sm text-gray-500">
                View database connection status and statistics.
              </p>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-500">Connection Status</p>
                  <p className="text-lg font-semibold text-success-600 flex items-center gap-2">
                    <span className="w-2 h-2 bg-success-500 rounded-full animate-pulse"></span>
                    Connected
                  </p>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-500">Database Type</p>
                  <p className="text-lg font-semibold text-gray-900">PostgreSQL 15</p>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-500">Cloud SQL Instance</p>
                  <p className="text-lg font-semibold text-gray-900">capitalspring-dev</p>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-500">Region</p>
                  <p className="text-lg font-semibold text-gray-900">us-central1</p>
                </div>
              </div>

              <div className="border-t pt-6">
                <h3 className="text-sm font-medium text-gray-700 mb-4">Table Statistics</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center p-4 bg-primary-50 rounded-lg">
                    <p className="text-3xl font-bold text-primary-600">0</p>
                    <p className="text-sm text-gray-500">Documents</p>
                  </div>
                  <div className="text-center p-4 bg-warning-50 rounded-lg">
                    <p className="text-3xl font-bold text-warning-600">0</p>
                    <p className="text-sm text-gray-500">Exceptions</p>
                  </div>
                  <div className="text-center p-4 bg-gray-100 rounded-lg">
                    <p className="text-3xl font-bold text-gray-600">0</p>
                    <p className="text-sm text-gray-500">Audit Logs</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
