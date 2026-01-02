import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Loader2, ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuthStore } from "@/store/auth"

const loginSchema = z.object({
  username: z.string().min(1, "Username is required"),
  password: z.string().min(1, "Password is required"),
})

type LoginForm = z.infer<typeof loginSchema>

export function LoginPage() {
  const navigate = useNavigate()
  const { login, isLoading } = useAuthStore()
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginForm) => {
    setError(null)
    try {
      await login(data)
      navigate("/")
    } catch {
      setError("Invalid username or password")
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-[480px] bg-slate-900 flex-col justify-between p-10">
        <div>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded bg-white/10 flex items-center justify-center">
              <ShieldCheck className="h-6 w-6 text-white" />
            </div>
            <span className="text-xl font-semibold text-white tracking-tight">COA System</span>
          </div>
        </div>

        <div className="space-y-6">
          <h1 className="text-3xl font-semibold text-white leading-tight">
            Certificate of Analysis<br />Management Platform
          </h1>
          <p className="text-slate-400 text-base leading-relaxed max-w-sm">
            Streamline quality control workflows with centralized test result tracking,
            automated COA generation, and comprehensive audit trails.
          </p>
        </div>

        <div className="text-sm text-slate-500">
          &copy; {new Date().getFullYear()} Quality Assurance Division
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center bg-slate-50 p-8">
        <div className="w-full max-w-sm">
          {/* Mobile Logo */}
          <div className="lg:hidden mb-8 flex items-center gap-3">
            <div className="h-10 w-10 rounded bg-slate-900 flex items-center justify-center">
              <ShieldCheck className="h-6 w-6 text-white" />
            </div>
            <span className="text-xl font-semibold text-slate-900 tracking-tight">COA System</span>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-slate-900">Sign in</h2>
            <p className="text-slate-600 mt-1">Enter your credentials to access the system</p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {error && (
              <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="username" className="text-slate-700 font-medium">
                Username
              </Label>
              <Input
                id="username"
                placeholder="Enter your username"
                className="h-11 bg-white border-slate-300 focus:border-slate-500 focus:ring-slate-500"
                {...register("username")}
                aria-invalid={!!errors.username}
              />
              {errors.username && (
                <p className="text-sm text-red-600">{errors.username.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-slate-700 font-medium">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your password"
                className="h-11 bg-white border-slate-300 focus:border-slate-500 focus:ring-slate-500"
                {...register("password")}
                aria-invalid={!!errors.password}
              />
              {errors.password && (
                <p className="text-sm text-red-600">{errors.password.message}</p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full h-11 bg-slate-900 hover:bg-slate-800 text-white font-medium"
              disabled={isLoading}
            >
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sign In
            </Button>
          </form>

          <p className="mt-8 text-center text-sm text-slate-500">
            Contact your administrator if you need access
          </p>
        </div>
      </div>
    </div>
  )
}
