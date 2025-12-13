import axios from 'axios'
import { auth } from '../lib/firebase'
import type {
  Document,
  DocumentListResponse,
  DocumentMetrics,
  Exception,
  ExceptionListResponse,
  ExceptionMetrics,
  DashboardMetrics,
  TrendData,
  ExportRequest,
  ExportResponse,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token interceptor
api.interceptors.request.use(
  async (config) => {
    const user = auth.currentUser
    if (user) {
      try {
        const token = await user.getIdToken()
        config.headers.Authorization = `Bearer ${token}`
      } catch (error) {
        console.error('Error getting auth token:', error)
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Handle 401 responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - redirect to login
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Documents API
export const documentsApi = {
  list: async (params?: {
    page?: number
    page_size?: number
    status?: string
    doc_type?: string
    requires_review?: boolean
    search?: string
  }): Promise<DocumentListResponse> => {
    const { data } = await api.get('/documents', { params })
    return data
  },

  get: async (id: string): Promise<Document> => {
    const { data } = await api.get(`/documents/${id}`)
    return data
  },

  upload: async (file: File, metadata?: { fund_id?: string; company_id?: string }) => {
    const formData = new FormData()
    formData.append('file', file)
    if (metadata?.fund_id) formData.append('fund_id', metadata.fund_id)
    if (metadata?.company_id) formData.append('company_id', metadata.company_id)

    const { data } = await api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  update: async (id: string, updates: Partial<Document>): Promise<Document> => {
    const { data } = await api.patch(`/documents/${id}`, updates)
    return data
  },

  reprocess: async (id: string, forceClaude?: boolean): Promise<Document> => {
    const { data } = await api.post(`/documents/${id}/reprocess`, null, {
      params: { force_claude: forceClaude },
    })
    return data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/documents/${id}`)
  },

  getMetrics: async (params?: {
    fund_id?: string
    date_from?: string
    date_to?: string
  }): Promise<DocumentMetrics> => {
    const { data } = await api.get('/documents/metrics', { params })
    return data
  },
}

// Exceptions API
export const exceptionsApi = {
  list: async (params?: {
    page?: number
    page_size?: number
    status?: string
    category?: string
    priority?: string
    document_id?: string
  }): Promise<ExceptionListResponse> => {
    const { data } = await api.get('/exceptions', { params })
    return data
  },

  get: async (id: string): Promise<Exception> => {
    const { data } = await api.get(`/exceptions/${id}`)
    return data
  },

  update: async (id: string, updates: Partial<Exception>): Promise<Exception> => {
    const { data } = await api.patch(`/exceptions/${id}`, updates)
    return data
  },

  resolve: async (
    id: string,
    resolution: {
      resolution: Record<string, unknown>
      resolution_notes?: string
      resolved_by: string
      apply_to_document?: boolean
    }
  ): Promise<Exception> => {
    const { data } = await api.post(`/exceptions/${id}/resolve`, resolution)
    return data
  },

  ignore: async (id: string, reason?: string): Promise<Exception> => {
    const { data } = await api.post(`/exceptions/${id}/ignore`, null, {
      params: { reason, ignored_by: 'user' },
    })
    return data
  },

  bulkResolve: async (
    ids: string[],
    resolution: {
      resolution: Record<string, unknown>
      resolution_notes?: string
      resolved_by: string
    }
  ): Promise<{ resolved_count: number; failed_ids: string[] }> => {
    const { data } = await api.post('/exceptions/bulk-resolve', {
      exception_ids: ids,
      ...resolution,
    })
    return data
  },

  getMetrics: async (params?: {
    date_from?: string
    date_to?: string
  }): Promise<ExceptionMetrics> => {
    const { data } = await api.get('/exceptions/metrics', { params })
    return data
  },
}

// Metrics API
export const metricsApi = {
  getDashboard: async (days?: number, fundId?: string): Promise<DashboardMetrics> => {
    const { data } = await api.get('/metrics/dashboard', {
      params: { days, fund_id: fundId },
    })
    return data
  },

  getTrends: async (
    days?: number,
    granularity?: 'day' | 'week' | 'month'
  ): Promise<TrendData> => {
    const { data } = await api.get('/metrics/trends', {
      params: { days, granularity },
    })
    return data
  },

  getProcessing: async (days?: number) => {
    const { data } = await api.get('/metrics/processing', {
      params: { days },
    })
    return data
  },
}

// Export API
export const exportApi = {
  getTemplates: async () => {
    const { data } = await api.get('/export/templates')
    return data
  },

  generateExcel: async (request: ExportRequest): Promise<ExportResponse> => {
    const { data } = await api.post('/export/excel', request)
    return data
  },

  generateBulk: async (request: {
    template: string
    format?: string
    doc_type?: string
    fund_id?: string
    date_from?: string
    date_to?: string
  }): Promise<ExportResponse> => {
    const { data } = await api.post('/export/bulk', request)
    return data
  },
}

// Health check
export const healthApi = {
  check: async () => {
    const { data } = await api.get('/health')
    return data
  },
}

export default api
