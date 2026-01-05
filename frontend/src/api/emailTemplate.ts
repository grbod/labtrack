import { api } from "./client"
import type {
  EmailTemplate,
  EmailTemplateUpdate,
  EmailTemplateVariablesResponse,
  EmailTemplatePreview,
} from "@/types/emailTemplate"

export const emailTemplateApi = {
  /**
   * Get the current email template configuration.
   */
  get: async (): Promise<EmailTemplate> => {
    const response = await api.get<EmailTemplate>("/settings/email-template")
    return response.data
  },

  /**
   * Update the email template.
   */
  update: async (data: EmailTemplateUpdate): Promise<EmailTemplate> => {
    const response = await api.put<EmailTemplate>("/settings/email-template", data)
    return response.data
  },

  /**
   * Reset the email template to defaults.
   */
  reset: async (): Promise<EmailTemplate> => {
    const response = await api.post<EmailTemplate>("/settings/email-template/reset")
    return response.data
  },

  /**
   * Get available template variables.
   */
  getVariables: async (): Promise<EmailTemplateVariablesResponse> => {
    const response = await api.get<EmailTemplateVariablesResponse>(
      "/settings/email-template/variables"
    )
    return response.data
  },

  /**
   * Preview the email template with sample data.
   */
  preview: async (data: EmailTemplateUpdate): Promise<EmailTemplatePreview> => {
    const response = await api.post<EmailTemplatePreview>(
      "/settings/email-template/preview",
      data
    )
    return response.data
  },
}
