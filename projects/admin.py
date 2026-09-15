from django.contrib import admin
from .models import Project, SubProject, KanbanColumn, Task, ProjectCredential


class SubProjectInline(admin.TabularInline):
    model = SubProject
    extra = 1
    show_change_link = True


class KanbanColumnInline(admin.TabularInline):
    model = KanbanColumn
    extra = 1


class ProjectCredentialInline(admin.StackedInline):
    model = ProjectCredential
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_by', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('members',)
    inlines = [SubProjectInline]


@admin.register(SubProject)
class SubProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'slug', 'created_at')
    list_filter = ('project',)
    search_fields = ('name', 'description')
    inlines = [KanbanColumnInline, ProjectCredentialInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'subproject', 'column', 'assigned_to', 'priority', 'due_date')
    list_filter = ('subproject', 'column', 'priority', 'assigned_to')
    search_fields = ('title', 'description')


@admin.register(ProjectCredential)
class ProjectCredentialAdmin(admin.ModelAdmin):
    list_display = ('title', 'subproject', 'service_url', 'username')
    list_filter = ('subproject',)
    search_fields = ('title', 'service_url', 'username')
