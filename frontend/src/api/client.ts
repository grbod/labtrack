import axios from "axios"
import type { Token, User, LoginCredentials, UserProfileUpdate } from "@/types"

const API_BASE_URL = "/api/v1"

// Create axios instance
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token")
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = localStorage.getItem("refresh_token")
      if (refreshToken) {
        try {
          const response = await axios.post<Token>(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          })

          const { access_token, refresh_token } = response.data
          localStorage.setItem("access_token", access_token)
          localStorage.setItem("refresh_token", refresh_token)

          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return api(originalRequest)
        } catch {
          // Refresh failed, clear tokens
          localStorage.removeItem("access_token")
          localStorage.removeItem("refresh_token")
          window.location.href = "/login"
        }
      }
    }

    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: async (credentials: LoginCredentials): Promise<Token> => {
    const formData = new URLSearchParams()
    formData.append("username", credentials.username)
    formData.append("password", credentials.password)

    const response = await api.post<Token>("/auth/login", formData, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    })
    return response.data
  },

  getMe: async (): Promise<User> => {
    const response = await api.get<User>("/auth/me")
    return response.data
  },

  logout: async (): Promise<void> => {
    await api.post("/auth/logout")
  },

  refresh: async (refreshToken: string): Promise<Token> => {
    const response = await api.post<Token>("/auth/refresh", {
      refresh_token: refreshToken,
    })
    return response.data
  },

  updateProfile: async (data: UserProfileUpdate): Promise<User> => {
    const response = await api.put<User>("/auth/me/profile", data)
    return response.data
  },

  uploadSignature: async (file: File): Promise<User> => {
    const formData = new FormData()
    formData.append("file", file)
    const response = await api.post<User>("/auth/me/signature", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    return response.data
  },

  deleteSignature: async (): Promise<User> => {
    const response = await api.delete<User>("/auth/me/signature")
    return response.data
  },

  verifyOverride: async (username: string, password: string): Promise<VerifyOverrideResponse> => {
    const formData = new URLSearchParams()
    formData.append("username", username)
    formData.append("password", password)

    const response = await api.post<VerifyOverrideResponse>("/auth/verify-override", formData, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    })
    return response.data
  },
}

export interface VerifyOverrideResponse {
  valid: boolean
  user_id: number | null
  role: string | null
  message: string
}
