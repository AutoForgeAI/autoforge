import { Sparkles, FileEdit, FolderOpen } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface ProjectSetupRequiredProps {
  projectName: string
  projectPath?: string
  onCreateWithClaude: () => void
  onEditManually: () => void
}

export function ProjectSetupRequired({
  projectName,
  projectPath,
  onCreateWithClaude,
  onEditManually,
}: ProjectSetupRequiredProps) {
  return (
    <div className="max-w-2xl mx-auto mt-8">
      <Card className="border-2">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-display">
            Project Setup Required
          </CardTitle>
          <CardDescription className="text-base">
            <span className="font-semibold">{projectName}</span> needs an app spec to get started
          </CardDescription>
          {projectPath && (
            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground mt-2">
              <FolderOpen size={14} />
              <code className="bg-muted px-2 py-0.5 rounded text-xs">{projectPath}</code>
            </div>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-center text-muted-foreground">
            Choose how you want to create your app specification:
          </p>

          <div className="grid gap-4 md:grid-cols-2">
            {/* Create with Claude Option */}
            <Card
              className="cursor-pointer border-2 transition-all hover:border-primary hover:shadow-md"
              onClick={onCreateWithClaude}
            >
              <CardContent className="pt-6 text-center space-y-3">
                <div className="w-12 h-12 mx-auto bg-primary/10 rounded-full flex items-center justify-center">
                  <Sparkles className="text-primary" size={24} />
                </div>
                <h3 className="font-semibold text-lg">Create with Claude</h3>
                <p className="text-sm text-muted-foreground">
                  Describe your app idea and Claude will help create a detailed specification
                </p>
                <Button className="w-full">
                  <Sparkles size={16} className="mr-2" />
                  Start Chat
                </Button>
              </CardContent>
            </Card>

            {/* Edit Manually Option */}
            <Card
              className="cursor-pointer border-2 transition-all hover:border-primary hover:shadow-md"
              onClick={onEditManually}
            >
              <CardContent className="pt-6 text-center space-y-3">
                <div className="w-12 h-12 mx-auto bg-muted rounded-full flex items-center justify-center">
                  <FileEdit className="text-muted-foreground" size={24} />
                </div>
                <h3 className="font-semibold text-lg">Edit Templates Manually</h3>
                <p className="text-sm text-muted-foreground">
                  Create the prompts directory and edit template files yourself
                </p>
                <Button variant="outline" className="w-full">
                  <FileEdit size={16} className="mr-2" />
                  View Templates
                </Button>
              </CardContent>
            </Card>
          </div>

          <p className="text-center text-xs text-muted-foreground pt-4">
            The app spec tells the agent what to build. It includes the application name,
            description, tech stack, and feature requirements.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
