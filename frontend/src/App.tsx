import { useEffect } from "react"
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import { useAuthStore } from "@/store/auth"
import { AppLayout } from "@/components/domain/AppLayout"
import { LoginPage } from "@/pages/Login"
import { DashboardPage } from "@/pages/Dashboard"
import { ProductsPage } from "@/pages/Products"
import { LabTestTypesPage } from "@/pages/LabTestTypes"
import { CreateSamplePage } from "@/pages/CreateSample"
import { SampleTrackerPage } from "@/pages/SampleTracker"
import { ApprovalsPage } from "@/pages/Approvals"
import { PublishPage } from "@/pages/Publish"
import { GridShowcasePage } from "@/pages/GridShowcase"
import { SettingsPage } from "@/pages/Settings"

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

function AppRoutes() {
  const { checkAuth, isAuthenticated } = useAuthStore()

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/login"
        element={
          isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />
        }
      />

      {/* Protected routes */}
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/products" element={<ProductsPage />} />
        <Route path="/lab-tests" element={<LabTestTypesPage />} />
        <Route path="/samples" element={<CreateSamplePage />} />
        <Route path="/tracker" element={<SampleTrackerPage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/publish" element={<PublishPage />} />
        <Route path="/grid-showcase" element={<GridShowcasePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      {/* Catch all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
