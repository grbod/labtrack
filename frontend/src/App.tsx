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
import { GridShowcasePage } from "@/pages/GridShowcase"
import { SettingsPage } from "@/pages/Settings"
import { CustomersPage } from "@/pages/Customers"
import { ReleaseQueuePage } from "@/pages/ReleaseQueue"
import { ReleasePage } from "@/pages/Release"
import { ArchivePage } from "@/pages/Archive"

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
        <Route path="/grid-showcase" element={<GridShowcasePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/release" element={<ReleaseQueuePage />} />
        <Route path="/release/:lotId/:productId" element={<ReleasePage />} />
        <Route path="/archive" element={<ArchivePage />} />
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
