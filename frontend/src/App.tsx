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
import { ImportResultsPage } from "@/pages/ImportResults"
import { ApprovalsPage } from "@/pages/Approvals"
import { PublishPage } from "@/pages/Publish"

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

// Placeholder pages for routes not yet implemented
function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-64">
      <h1 className="text-2xl font-bold mb-2">{title}</h1>
      <p className="text-muted-foreground">Coming soon...</p>
    </div>
  )
}

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
        <Route path="/import" element={<ImportResultsPage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/publish" element={<PublishPage />} />
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
