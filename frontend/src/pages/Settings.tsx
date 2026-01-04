import { useState, useEffect } from "react"
import { Settings as SettingsIcon, Building2, AlertTriangle, Eye, Save, Loader2, Upload } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

import { useAuthStore } from "@/store/auth"
import { useSettings, PAGE_SIZE_OPTIONS } from "@/hooks/useSettings"

export function SettingsPage() {
  const { user } = useAuthStore()
  const { user: userSettings, system: systemSettings, canEditSystemSettings } = useSettings(
    user?.username,
    user?.role
  )

  // Local form state for system settings
  const [staleWarningDays, setStaleWarningDays] = useState(systemSettings.settings.staleWarningDays)
  const [staleCriticalDays, setStaleCriticalDays] = useState(systemSettings.settings.staleCriticalDays)
  const [recentlyCompletedDays, setRecentlyCompletedDays] = useState(systemSettings.settings.recentlyCompletedDays)
  const [companyName, setCompanyName] = useState(systemSettings.settings.labInfo.companyName)
  const [address, setAddress] = useState(systemSettings.settings.labInfo.address)
  const [phone, setPhone] = useState(systemSettings.settings.labInfo.phone)
  const [email, setEmail] = useState(systemSettings.settings.labInfo.email)

  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Sync local state when settings change
  useEffect(() => {
    setStaleWarningDays(systemSettings.settings.staleWarningDays)
    setStaleCriticalDays(systemSettings.settings.staleCriticalDays)
    setRecentlyCompletedDays(systemSettings.settings.recentlyCompletedDays)
    setCompanyName(systemSettings.settings.labInfo.companyName)
    setAddress(systemSettings.settings.labInfo.address)
    setPhone(systemSettings.settings.labInfo.phone)
    setEmail(systemSettings.settings.labInfo.email)
  }, [systemSettings.settings])

  const handlePageSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = parseInt(e.target.value, 10)
    userSettings.updateSettings({ pageSize: value })
  }

  const handleSaveSystemSettings = async () => {
    setIsSaving(true)
    setSaveSuccess(false)

    // Validate thresholds
    const warning = Math.max(1, staleWarningDays)
    const critical = Math.max(warning + 1, staleCriticalDays)
    const recentlyCompleted = Math.max(1, recentlyCompletedDays)

    systemSettings.updateSettings({
      staleWarningDays: warning,
      staleCriticalDays: critical,
      recentlyCompletedDays: recentlyCompleted,
      labInfo: {
        companyName,
        address,
        phone,
        email,
        logoUrl: systemSettings.settings.labInfo.logoUrl,
      },
    })

    // Simulate async save (will be real API call later)
    await new Promise((resolve) => setTimeout(resolve, 300))

    setIsSaving(false)
    setSaveSuccess(true)
    setTimeout(() => setSaveSuccess(false), 2000)
  }

  const hasSystemChanges =
    staleWarningDays !== systemSettings.settings.staleWarningDays ||
    staleCriticalDays !== systemSettings.settings.staleCriticalDays ||
    recentlyCompletedDays !== systemSettings.settings.recentlyCompletedDays ||
    companyName !== systemSettings.settings.labInfo.companyName ||
    address !== systemSettings.settings.labInfo.address ||
    phone !== systemSettings.settings.labInfo.phone ||
    email !== systemSettings.settings.labInfo.email

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Settings</h1>
        <p className="mt-1.5 text-[15px] text-slate-500">
          Manage your display preferences and system configuration
        </p>
      </div>

      {/* Display Preferences - All Users */}
      <Card className="border-slate-200/60 shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100">
              <Eye className="h-5 w-5 text-slate-600" />
            </div>
            <div>
              <CardTitle className="text-[16px] font-semibold text-slate-900">
                Display Preferences
              </CardTitle>
              <CardDescription className="text-[13px] text-slate-500">
                Customize how data is displayed throughout the application
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="max-w-sm">
            <Label
              htmlFor="pageSize"
              className="text-[13px] font-semibold text-slate-700"
            >
              Items per page
            </Label>
            <div className="mt-1.5 flex items-center gap-3">
              <select
                id="pageSize"
                value={userSettings.settings.pageSize}
                onChange={handlePageSizeChange}
                className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-[14px] text-slate-900 shadow-sm focus:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>
                    {size} items
                  </option>
                ))}
              </select>
              <span className="text-[13px] text-slate-500">per page</span>
            </div>
            <p className="mt-2 text-[12px] text-slate-500">
              Controls the number of items shown in tables and lists
            </p>
          </div>
        </CardContent>
      </Card>

      {/* System Settings - Admin/QC Manager Only */}
      {canEditSystemSettings && (
        <Card className="border-slate-200/60 shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100">
                <SettingsIcon className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <CardTitle className="text-[16px] font-semibold text-slate-900">
                  System Settings
                </CardTitle>
                <CardDescription className="text-[13px] text-slate-500">
                  Configure global settings for the COA system
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-2 space-y-8">
            {/* Stale Thresholds */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <h3 className="text-[14px] font-semibold text-slate-800">
                  Sample Tracker Thresholds
                </h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-2xl">
                <div className="space-y-1.5">
                  <Label
                    htmlFor="staleWarning"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Stale Warning (days)
                  </Label>
                  <Input
                    id="staleWarning"
                    type="number"
                    min={1}
                    value={staleWarningDays}
                    onChange={(e) => setStaleWarningDays(parseInt(e.target.value, 10) || 1)}
                    className="h-10 border-slate-200"
                  />
                  <p className="text-[11px] text-slate-500">
                    Samples older than this show orange warning
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label
                    htmlFor="staleCritical"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Stale Critical (days)
                  </Label>
                  <Input
                    id="staleCritical"
                    type="number"
                    min={staleWarningDays + 1}
                    value={staleCriticalDays}
                    onChange={(e) => setStaleCriticalDays(parseInt(e.target.value, 10) || staleWarningDays + 1)}
                    className="h-10 border-slate-200"
                  />
                  <p className="text-[11px] text-slate-500">
                    Samples older than this show red critical
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label
                    htmlFor="recentlyCompleted"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Recently Completed (days)
                  </Label>
                  <Input
                    id="recentlyCompleted"
                    type="number"
                    min={1}
                    value={recentlyCompletedDays}
                    onChange={(e) => setRecentlyCompletedDays(parseInt(e.target.value, 10) || 7)}
                    className="h-10 border-slate-200"
                  />
                  <p className="text-[11px] text-slate-500">
                    Show completed samples from the last X days
                  </p>
                </div>
              </div>
            </div>

            {/* Lab Information */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Building2 className="h-4 w-4 text-blue-500" />
                <h3 className="text-[14px] font-semibold text-slate-800">
                  Lab Information
                </h3>
              </div>
              <p className="text-[12px] text-slate-500 mb-4">
                This information will appear on generated Certificates of Analysis
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl">
                <div className="sm:col-span-2 space-y-1.5">
                  <Label
                    htmlFor="companyName"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Company Name
                  </Label>
                  <Input
                    id="companyName"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="Enter company name"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="sm:col-span-2 space-y-1.5">
                  <Label
                    htmlFor="address"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Address
                  </Label>
                  <Input
                    id="address"
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    placeholder="Enter full address"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label
                    htmlFor="phone"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Phone
                  </Label>
                  <Input
                    id="phone"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="Enter phone number"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label
                    htmlFor="email"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Email
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter email address"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="sm:col-span-2 space-y-1.5">
                  <Label className="text-[13px] font-semibold text-slate-700">
                    Company Logo
                  </Label>
                  <div className="flex items-center gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      disabled
                      className="h-10 border-slate-200 text-slate-500"
                    >
                      <Upload className="h-4 w-4 mr-2" />
                      Upload Logo
                    </Button>
                    <span className="text-[12px] text-slate-400">
                      Coming soon - Logo upload will be available in a future update
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Save Button */}
            <div className="pt-4 border-t border-slate-100">
              <div className="flex items-center gap-3">
                <Button
                  onClick={handleSaveSystemSettings}
                  disabled={isSaving || !hasSystemChanges}
                  className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10 px-5"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save Changes
                    </>
                  )}
                </Button>
                {saveSuccess && (
                  <span className="text-[13px] font-medium text-emerald-600">
                    Settings saved successfully
                  </span>
                )}
                {!hasSystemChanges && !saveSuccess && (
                  <span className="text-[12px] text-slate-400">
                    No unsaved changes
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
