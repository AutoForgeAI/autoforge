/**
 * Existing Project Setup Component
 *
 * Shows appropriate setup options when a project has code artifacts but no spec.
 * Detects existing projects and offers:
 * - Add new features (Expand Project)
 * - Create fresh spec (Spec Wizard)
 * - Review/document existing code (Doc Admin)
 */

import { Plus, Sparkles, FileSearch, FolderOpen, Code, GitBranch, Database, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { ProjectArtifacts } from '@/lib/types'

interface ExistingProjectSetupProps {
  projectName: string
  projectPath?: string
  artifacts: ProjectArtifacts
  onExpandProject: () => void
  onCreateSpec: () => void
  onDocAdmin: () => void
}

export function ExistingProjectSetup({
  projectName,
  projectPath,
  artifacts,
  onExpandProject,
  onCreateSpec,
  onDocAdmin,
}: ExistingProjectSetupProps) {
  // Determine if this looks like a fully-built project
  const isExistingProject = artifacts.has_code || artifacts.has_claude_md || artifacts.has_features_db

  return (
    <div className="max-w-3xl mx-auto mt-8">
      <Card className="border-2">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-display">
            {isExistingProject ? 'Existing Project Detected' : 'Project Setup Required'}
          </CardTitle>
          <CardDescription className="text-base">
            <span className="font-semibold">{projectName}</span>
            {isExistingProject
              ? ' appears to be an existing codebase'
              : ' needs an app spec to get started'}
          </CardDescription>
          {projectPath && (
            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground mt-2">
              <FolderOpen size={14} />
              <code className="bg-muted px-2 py-0.5 rounded text-xs">{projectPath}</code>
            </div>
          )}

          {/* Artifact badges */}
          {isExistingProject && (
            <div className="flex flex-wrap justify-center gap-2 mt-4">
              {artifacts.has_git && (
                <Badge variant="outline" className="gap-1">
                  <GitBranch size={12} />
                  Git repo
                </Badge>
              )}
              {artifacts.has_code && (
                <Badge variant="outline" className="gap-1">
                  <Code size={12} />
                  Code detected
                </Badge>
              )}
              {artifacts.has_claude_md && (
                <Badge variant="outline" className="gap-1">
                  <FileText size={12} />
                  CLAUDE.md
                </Badge>
              )}
              {artifacts.has_features_db && (
                <Badge variant="outline" className="gap-1">
                  <Database size={12} />
                  {artifacts.feature_count} features
                </Badge>
              )}
            </div>
          )}

          {/* Code indicators */}
          {artifacts.code_indicators.length > 0 && (
            <div className="text-xs text-muted-foreground mt-2">
              Found: {artifacts.code_indicators.slice(0, 5).join(', ')}
              {artifacts.code_indicators.length > 5 && ` +${artifacts.code_indicators.length - 5} more`}
            </div>
          )}
        </CardHeader>

        <CardContent className="space-y-4">
          <p className="text-center text-muted-foreground">
            {isExistingProject
              ? 'Choose how you want to work with this project:'
              : 'Choose how you want to create your app specification:'}
          </p>

          <div className={`grid gap-4 ${isExistingProject ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
            {/* Expand Project - only for existing projects */}
            {isExistingProject && (
              <Card
                className="cursor-pointer border-2 transition-all hover:border-primary hover:shadow-md"
                onClick={onExpandProject}
              >
                <CardContent className="pt-6 text-center space-y-3">
                  <div className="w-12 h-12 mx-auto bg-green-500/10 rounded-full flex items-center justify-center">
                    <Plus className="text-green-600" size={24} />
                  </div>
                  <h3 className="font-semibold text-lg">Add New Features</h3>
                  <p className="text-sm text-muted-foreground">
                    Describe new features to add to your existing project
                  </p>
                  <Button className="w-full bg-green-600 hover:bg-green-700">
                    <Plus size={16} className="mr-2" />
                    Expand Project
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Create Spec with Claude */}
            <Card
              className="cursor-pointer border-2 transition-all hover:border-primary hover:shadow-md"
              onClick={onCreateSpec}
            >
              <CardContent className="pt-6 text-center space-y-3">
                <div className="w-12 h-12 mx-auto bg-primary/10 rounded-full flex items-center justify-center">
                  <Sparkles className="text-primary" size={24} />
                </div>
                <h3 className="font-semibold text-lg">
                  {isExistingProject ? 'Create Fresh Spec' : 'Create with Claude'}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {isExistingProject
                    ? 'Start fresh with a new app specification'
                    : 'Describe your app and Claude will create a detailed spec'}
                </p>
                <Button variant={isExistingProject ? 'outline' : 'default'} className="w-full">
                  <Sparkles size={16} className="mr-2" />
                  {isExistingProject ? 'Start Fresh' : 'Start Chat'}
                </Button>
              </CardContent>
            </Card>

            {/* Doc Admin - only for existing projects */}
            {isExistingProject && (
              <Card
                className="cursor-pointer border-2 transition-all hover:border-primary hover:shadow-md"
                onClick={onDocAdmin}
              >
                <CardContent className="pt-6 text-center space-y-3">
                  <div className="w-12 h-12 mx-auto bg-blue-500/10 rounded-full flex items-center justify-center">
                    <FileSearch className="text-blue-600" size={24} />
                  </div>
                  <h3 className="font-semibold text-lg">Review & Document</h3>
                  <p className="text-sm text-muted-foreground">
                    Analyze existing code and generate documentation
                  </p>
                  <Button variant="outline" className="w-full">
                    <FileSearch size={16} className="mr-2" />
                    Run Doc Admin
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>

          <p className="text-center text-xs text-muted-foreground pt-4">
            {isExistingProject
              ? 'The spec defines features for the agent to implement. Expand adds to existing code.'
              : 'The app spec tells the agent what to build. It includes the application name, description, tech stack, and feature requirements.'}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
