import { useState } from 'react'
import { Loader2, UserCircle, Send } from 'lucide-react'
import type { HumanInputRequest } from '../lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Switch } from '@/components/ui/switch'

interface HumanInputFormProps {
  request: HumanInputRequest
  onSubmit: (fields: Record<string, string | boolean | string[]>) => Promise<void>
  isLoading: boolean
}

export function HumanInputForm({ request, onSubmit, isLoading }: HumanInputFormProps) {
  const [values, setValues] = useState<Record<string, string | boolean | string[]>>(() => {
    const initial: Record<string, string | boolean | string[]> = {}
    for (const field of request.fields) {
      if (field.type === 'boolean') {
        initial[field.id] = false
      } else {
        initial[field.id] = ''
      }
    }
    return initial
  })

  const [validationError, setValidationError] = useState<string | null>(null)

  const handleSubmit = async () => {
    // Validate required fields
    for (const field of request.fields) {
      if (field.required) {
        const val = values[field.id]
        if (val === undefined || val === null || val === '') {
          setValidationError(`"${field.label}" is required`)
          return
        }
      }
    }
    setValidationError(null)
    await onSubmit(values)
  }

  return (
    <Alert className="border-amber-500 bg-amber-50 dark:bg-amber-950/20">
      <UserCircle className="h-5 w-5 text-amber-600" />
      <AlertDescription className="space-y-4">
        <div>
          <h4 className="font-semibold text-amber-700 dark:text-amber-400">Agent needs your help</h4>
          <p className="text-sm text-amber-600 dark:text-amber-300 mt-1">
            {request.prompt}
          </p>
        </div>

        <div className="space-y-3">
          {request.fields.map((field) => (
            <div key={field.id} className="space-y-1.5">
              <Label htmlFor={`human-input-${field.id}`} className="text-sm font-medium text-foreground">
                {field.label}
                {field.required && <span className="text-destructive ml-1">*</span>}
              </Label>

              {field.type === 'text' && (
                <Input
                  id={`human-input-${field.id}`}
                  value={values[field.id] as string}
                  onChange={(e) => setValues(prev => ({ ...prev, [field.id]: e.target.value }))}
                  placeholder={field.placeholder || ''}
                  disabled={isLoading}
                />
              )}

              {field.type === 'textarea' && (
                <Textarea
                  id={`human-input-${field.id}`}
                  value={values[field.id] as string}
                  onChange={(e) => setValues(prev => ({ ...prev, [field.id]: e.target.value }))}
                  placeholder={field.placeholder || ''}
                  disabled={isLoading}
                  rows={3}
                />
              )}

              {field.type === 'select' && field.options && (
                <div className="space-y-1.5">
                  {field.options.map((option) => (
                    <label
                      key={option.value}
                      className={`flex items-center gap-2 p-2 rounded-md border cursor-pointer transition-colors
                        ${values[field.id] === option.value
                          ? 'border-primary bg-primary/10'
                          : 'border-border hover:border-primary/50'}`}
                    >
                      <input
                        type="radio"
                        name={`human-input-${field.id}`}
                        value={option.value}
                        checked={values[field.id] === option.value}
                        onChange={(e) => setValues(prev => ({ ...prev, [field.id]: e.target.value }))}
                        disabled={isLoading}
                        className="accent-primary"
                      />
                      <span className="text-sm">{option.label}</span>
                    </label>
                  ))}
                </div>
              )}

              {field.type === 'boolean' && (
                <div className="flex items-center gap-2">
                  <Switch
                    id={`human-input-${field.id}`}
                    checked={values[field.id] as boolean}
                    onCheckedChange={(checked) => setValues(prev => ({ ...prev, [field.id]: checked }))}
                    disabled={isLoading}
                  />
                  <Label htmlFor={`human-input-${field.id}`} className="text-sm">
                    {values[field.id] ? 'Yes' : 'No'}
                  </Label>
                </div>
              )}
            </div>
          ))}
        </div>

        {validationError && (
          <p className="text-sm text-destructive">{validationError}</p>
        )}

        <Button
          onClick={handleSubmit}
          disabled={isLoading}
          className="w-full"
        >
          {isLoading ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <>
              <Send size={16} />
              Submit Response
            </>
          )}
        </Button>
      </AlertDescription>
    </Alert>
  )
}
