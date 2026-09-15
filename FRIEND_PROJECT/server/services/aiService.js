import { GoogleGenAI, Type } from '@google/genai'

export async function analyzeComplaint({ title, description, address, availableDepartments }) {
  if (!process.env.GEMINI_API_KEY) {
    throw new Error('GEMINI_API_KEY is not defined in server/.env')
  }

  const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY })

  const prompt = `
You are an expert civic infrastructure AI assistant.
Analyze this civic complaint and provide structured triage data.

Complaint Title: ${title}
Description: ${description}
Location context: ${address || 'Not provided'}
Available Government Departments: ${availableDepartments.map((d) => `"${d.name}" (ID: ${d.id})`).join(', ')}

Analyze the severity (0 to 100), choose the most relevant department from the provided list, estimate realistic resolution days, categorize the issue, and provide concise reasoning.
`

  const response = await ai.models.generateContent({
    model: 'gemini-3.6-flash',
    contents: prompt,
    config: {
      responseMimeType: 'application/json',
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          category: { type: Type.STRING },
          subcategory: { type: Type.STRING },
          severity_score: { type: Type.INTEGER },
          priority: { type: Type.STRING, enum: ['low', 'medium', 'high', 'critical'] },
          recommended_department_id: { type: Type.STRING },
          estimated_resolution_days: { type: Type.INTEGER },
          ai_summary: { type: Type.STRING },
          reasoning: { type: Type.STRING },
        },
        required: [
          'category',
          'subcategory',
          'severity_score',
          'priority',
          'recommended_department_id',
          'estimated_resolution_days',
          'ai_summary',
          'reasoning',
        ],
      },
    },
  })

  return JSON.parse(response.text)
}