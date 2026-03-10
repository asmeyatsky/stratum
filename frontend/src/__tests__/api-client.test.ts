import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import api, { ApiError } from '../api/client';

describe('API Client', () => {
  it('getProjects returns list of projects', async () => {
    const projects = await api.getProjects();
    expect(projects).toHaveLength(2);
    expect(projects[0].name).toBe('Backend API');
    expect(projects[1].name).toBe('Frontend App');
  });

  it('getProject returns a single project', async () => {
    const project = await api.getProject('proj-1');
    expect(project.id).toBe('proj-1');
    expect(project.name).toBe('Backend API');
    expect(project.health_score).toBe(7.2);
  });

  it('createProject sends payload and returns new project', async () => {
    const project = await api.createProject({
      name: 'New Service',
      scenario: 'tech-debt',
    });
    expect(project.id).toBe('proj-new');
    expect(project.name).toBe('New Service');
    expect(project.status).toBe('pending');
  });

  it('deleteProject completes without error', async () => {
    await expect(api.deleteProject('proj-1')).resolves.toBeUndefined();
  });

  it('throws ApiError on 404', async () => {
    server.use(
      http.get('/api/projects/:id', () => {
        return new HttpResponse('Not Found', { status: 404 });
      }),
    );

    await expect(api.getProject('nonexistent')).rejects.toThrow(ApiError);
    await expect(api.getProject('nonexistent')).rejects.toMatchObject({
      status: 404,
    });
  });

  it('throws ApiError on 500', async () => {
    server.use(
      http.get('/api/projects', () => {
        return new HttpResponse('Internal Server Error', { status: 500 });
      }),
    );

    await expect(api.getProjects()).rejects.toThrow(ApiError);
    await expect(api.getProjects()).rejects.toMatchObject({
      status: 500,
    });
  });

  it('getReport returns analysis report', async () => {
    const report = await api.getReport('proj-1');
    expect(report.health_score).toBe(7.2);
    expect(report.dimensions).toHaveLength(3);
    expect(report.components).toHaveLength(2);
    expect(report.hotspots).toHaveLength(2);
    expect(report.trends).toHaveLength(5);
    expect(report.summary).toBeTruthy();
  });

  it('getDimensions returns dimension scores', async () => {
    const dimensions = await api.getDimensions('proj-1');
    expect(dimensions).toHaveLength(3);
    expect(dimensions[0].name).toBe('Code Complexity');
  });

  it('getComponents returns component risks', async () => {
    const components = await api.getComponents('proj-1');
    expect(components).toHaveLength(2);
    expect(components[0].name).toBe('auth-service');
  });

  it('getHotspots returns file hotspots', async () => {
    const hotspots = await api.getHotspots('proj-1');
    expect(hotspots).toHaveLength(2);
    expect(hotspots[0].file_path).toBe('src/services/auth/handler.ts');
  });

  it('getTrends returns feature/bug trends', async () => {
    const trends = await api.getTrends('proj-1');
    expect(trends).toHaveLength(5);
    expect(trends[0].period).toBe('2026-01-01');
  });
});
