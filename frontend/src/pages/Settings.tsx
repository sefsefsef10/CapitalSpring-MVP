import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Save,
  RefreshCw,
  FileText,
  Shield,
  Bell,
  Database,
  Zap,
} from 'lucide-react'
import clsx from 'clsx'
import api from '../services/api'

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

interface AllSettings {
  processing: ProcessorConfig
  validation: ValidationConfig
  notifications: NotificationConfig
}

interface DatabaseStats {
  documents_count: number
  exceptions_count: number
  audit_logs_count: number
  connection_status: string
  database_type: string
  instance_name: string
  region: string
}

interface DocumentTypeInfo {
  type: string
  processor: string
  fallback: string
  status: string
}

export default function Settings() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('processing')
  const [hasChanges, setHasChanges] = useState(false)

  // Fetch all settings
  const { data: settings, isLoading: settingsLoading } = useQuery<AllSettings>({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await api.get('/settings')
      return response.data
    },
  })

  // Fetch database stats
  const { data: dbStats, isLoading: dbLoading } = useQuery<DatabaseStats>({
    queryKey: ['settings', 'database'],
    queryFn: async () => {
      const response = await api.get('/settings/database')
      return response.data
    },
  })

  // Fetch document types
  const { data: documentTypes, isLoading: docTypesLoading } = useQuery<DocumentTypeInfo[]>({
    queryKey: ['settings', 'document-types'],
    queryFn: async () => {
      const response = await api.get('/settings/document-types')
      return response.data
    },
  })

  // Local state for editing
  const [processorConfig, setProcessorConfig] = useState<ProcessorConfig>({
    confidence_threshold: 0.85,
    fallback_to_claude: true,
    max_retries: 3,
  })

  const [validationConfig, setValidationConfig] = useState<ValidationConfig>({
    strict_mode: true,
    required_fields_only: false,
    auto_create_exceptions: true,
  })

  const [notificationConfig, setNotificationConfig] = useState<NotificationConfig>({
    email_on_exception: true,
    email_on_batch_complete: false,
    slack_webhook_url: '',
  })

  // Update local state when settings load
  useEffect(() => {
    if (settings) {
      setProcessorConfig(settings.processing)
      setValidationConfig(settings.validation)
      setNotificationConfig(settings.notifications)
      setHasChanges(false)
    }
  }, [settings])

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async () => {
      const response = await api.put('/settings', {
        processing: processorConfig,
        validation: validationConfig,
        notifications: notificationConfig,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      toast.success('Settings saved successfully')
      setHasChanges(false)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to save settings')
    },
  })

  const handleSave = () => {
    saveMutation.mutate()
  }

  // Track changes
  const updateProcessorConfig = (updates: Partial<ProcessorConfig>) => {
    setProcessorConfig({ ...processorConfig, ...updates })
    setHasChanges(true)
  }

  const updateValidationConfig = (updates: Partial<ValidationConfig>) => {
    setValidationConfig({ ...validationConfig, ...updates })
    setHasChanges(true)
  }

  const updateNotificationConfig = (updates: Partial<NotificationConfig>) => {
    setNotificationConfig({ ...notificationConfig, ...updates })
    setHasChanges(true)
  }

  const tabs = [
    { id: 'processing', label: 'Processing', icon: Zap },
    { id: 'validation', label: 'Validation', icon: Shield },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'documents', label: 'Document Types', icon: FileText },
    { id: 'database', label: 'Database', icon: Database },
  ]

  if (settingsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-500">Configure system preferences and processing rules</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending || !hasChanges}
          className={clsx(
            'btn-primary',
            !hasChanges && 'opacity-50 cursor-not-allowed'
          )}
        >
          {saveMutation.isPending ? (
            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Save className="w-4 h-4 mr-2" />
          )}
          {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
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
                        updateProcessorConfig({
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
                      updateProcessorConfig({
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
                      updateProcessorConfig({
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
                      updateValidationConfig({
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
                      updateValidationConfig({
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
                      updateValidationConfig({
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
                      updateNotificationConfig({
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
                      updateNotificationConfig({
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
                      updateNotificationConfig({
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

              {docTypesLoading ? (
                <div className="flex items-center justify-center h-32">
                  <RefreshCw className="w-6 h-6 animate-spin text-primary-500" />
                </div>
              ) : (
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
                      {(documentTypes || []).map((doc, idx) => (
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
              )}
            </div>
          )}

          {activeTab === 'database' && (
            <div className="card p-6 space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Database Information</h2>
              <p className="text-sm text-gray-500">
                View database connection status and statistics.
              </p>

              {dbLoading ? (
                <div className="flex items-center justify-center h-32">
                  <RefreshCw className="w-6 h-6 animate-spin text-primary-500" />
                </div>
              ) : dbStats ? (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 bg-gray-50 rounded-lg">
                      <p className="text-sm text-gray-500">Connection Status</p>
                      <p className={clsx(
                        'text-lg font-semibold flex items-center gap-2',
                        dbStats.connection_status === 'connected' ? 'text-success-600' : 'text-error-600'
                      )}>
                        <span className={clsx(
                          'w-2 h-2 rounded-full',
                          dbStats.connection_status === 'connected' ? 'bg-success-500 animate-pulse' : 'bg-error-500'
                        )}></span>
                        {dbStats.connection_status === 'connected' ? 'Connected' : 'Error'}
                      </p>
                    </div>
                    <div className="p-4 bg-gray-50 rounded-lg">
                      <p className="text-sm text-gray-500">Database Type</p>
                      <p className="text-lg font-semibold text-gray-900">{dbStats.database_type}</p>
                    </div>
                    <div className="p-4 bg-gray-50 rounded-lg">
                      <p className="text-sm text-gray-500">Cloud SQL Instance</p>
                      <p className="text-lg font-semibold text-gray-900">{dbStats.instance_name}</p>
                    </div>
                    <div className="p-4 bg-gray-50 rounded-lg">
                      <p className="text-sm text-gray-500">Region</p>
                      <p className="text-lg font-semibold text-gray-900">{dbStats.region}</p>
                    </div>
                  </div>

                  <div className="border-t pt-6">
                    <h3 className="text-sm font-medium text-gray-700 mb-4">Table Statistics</h3>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="text-center p-4 bg-primary-50 rounded-lg">
                        <p className="text-3xl font-bold text-primary-600">{dbStats.documents_count}</p>
                        <p className="text-sm text-gray-500">Documents</p>
                      </div>
                      <div className="text-center p-4 bg-warning-50 rounded-lg">
                        <p className="text-3xl font-bold text-warning-600">{dbStats.exceptions_count}</p>
                        <p className="text-sm text-gray-500">Exceptions</p>
                      </div>
                      <div className="text-center p-4 bg-gray-100 rounded-lg">
                        <p className="text-3xl font-bold text-gray-600">{dbStats.audit_logs_count}</p>
                        <p className="text-sm text-gray-500">Audit Logs</p>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-gray-500">Unable to load database stats</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
