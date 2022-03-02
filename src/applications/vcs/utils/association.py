# -*- coding: utf-8 -*-
from django.db.models import Q
from django.db.models.functions import Lower
from applications.api.testing.stop_words import stop_words
from applications.api.testing.wordinflector import WordInflector
from applications.vcs.utils.analysis import find_similarity_in_name, similarity
# from applications.vcs.models import Area, File
# from applications.testing.models import Test



def find_and_associate_areas(test_instance):
    from applications.vcs.models import Area
    test_args = ['name', 'class_name', 'testsuite_name']

    associated_areas = list(test_instance.associated_areas.all().values('id', 'name'))

    project_areas = Area.objects.filter(
        Q(project=test_instance.project) & ~Q(name='Default Area')
    ).exclude(id__in=(x['id'] for x in associated_areas))

    project_areas = project_areas.exclude(name__in=stop_words)
    project_areas = list(project_areas.values('id', 'name', ))

    for area in project_areas:
        for arg in test_args:
            name = getattr(test_instance, arg)
            area[arg + '_similarity'] = 0 if name is None else similarity(name, area['name'])

    # Find 5 areas that most closely match the test's name/class_name/testsuite_name
    similar_areas = find_similarity_in_name(project_areas)
    matched_areas = list()
    for arg in test_args:
        for area in similar_areas[arg]:
            if area['id'] not in matched_areas:
                matched_areas.append(area['id'])

    areas = Area.objects.filter(id__in=matched_areas[:15])
    # test_instance.associated_areas.add(*areas)
    through_model = test_instance.associated_areas.through
    through_model.objects.bulk_create([
        through_model(test_id=test_instance.id, area_id=area_id)
        for area_id in list(areas.exclude(associated_areas__id=test_instance.id).values_list('id', flat=True))
    ])
    return True


def find_and_association_files(test_instance):
    from applications.vcs.models import File
    test_args = ['name', 'class_name', 'testsuite_name']
    associated_files = list(test_instance.associated_files.exclude(sha='').values('id', 'filename', 'full_filename'))
    query = Q(project=test_instance.project) & ~Q(sha='') & ~Q(id__in=(x['id'] for x in associated_files))
    project_files = File.objects.exclude(filename__in=stop_words)
    project_files = list(project_files.filter(query).values('id', 'filename', 'full_filename', ))
    project_folders = list()

    for file in project_files:
        for arg in test_args:
            name = getattr(test_instance, arg)
            file[arg + '_similarity'] = 0 if name is None else similarity(name, file['filename'])
        folder_path = file['full_filename'].replace('/' + file['filename'], '') if '/' in file['full_filename'] else ''
        folders = folder_path.split('/')
        file['parent_folder'] = None
        if len(folders) > 0:
            file['parent_folder'] = folders[len(folders) - 1]
        for folder in folders:
            project_folders.append({
                'file_id': file['id'],
                'folder_name': folder,
            })

    for folder in project_folders:
        for arg in test_args:
            name = getattr(test_instance, arg)
            folder[arg + '_similarity'] = 0 if name is None else similarity(name, folder['folder_name'])

    # Find 5 files/folders that most closely match the test's name/class_name/testsuite_name
    similar_files = find_similarity_in_name(project_files)
    similar_folders = find_similarity_in_name(project_folders)
    matched_files = list()

    # For the similar_files check which is the parent folder for these files and add those to similar_folders
    for arg in test_args:
        for file in similar_files[arg]:
            if file['parent_folder'] is not None:
                similar_folders[arg].append({
                    'file_id': file['id'],
                    'folder_name': file['parent_folder']
                })
            if file['id'] not in matched_files:
                matched_files.append(file['id'])

    files = File.objects.filter(id__in=matched_files[:15])
    # test_instance.associated_files.add(*files)
    through_model = test_instance.associated_files.through
    through_model.objects.bulk_create([
        through_model(test_id=test_instance.id, file_id=file_id)
        for file_id in list(files.exclude(associated_files__id=test_instance.id).values_list('id', flat=True))
    ])
    return True
