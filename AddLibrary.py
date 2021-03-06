import sublime, sublime_plugin
import os, re
import threading
import json

from .Libraries import Libraries

try:
	from urllib.request import urlopen, Request
except ImportError:
	from urllib2 import urlopen, URLError

def downloadLib(folder, lib):
	settings = sublime.load_settings("AddLibrary.sublime-settings") 
	default_lib = settings.get("default_folder")
	
	if not os.path.exists(folder + default_lib):
		os.makedirs(folder + default_lib)

	nf = GetLibThread(lib, folder + default_lib)
	nf.start()

# global http get
def httpGet(url):
	request_obj = Request(url, method='GET')
	req = urlopen(url=request_obj)
	return req

class AddLibrary(sublime_plugin.TextCommand):

	def __init__(self, view):
		self.view = view
		self.window = sublime.active_window()
		self.folder_path = self.window.folders()

	def run(self, edit):
		self.libraries_names = Libraries().getLibrariesName()
		self.install_on_folder = None
		self.selected_lib = None
		
		arr_to_list = []
		for ln in self.libraries_names:
			arr_to_list.append("Download - "+ln)

		# select a lib to download
		self.window.show_quick_panel(arr_to_list, self.selectedLibrary)

	def selectedLibrary(self, option_index):
		if option_index > -1:
			self.selected_lib = Libraries().getLibraryByName(self.libraries_names[option_index])
			self.folder_path = self.window.folders()

			# if have more than a active folder in sublime
			if len(self.folder_path) > 1:
				name_of_folders = self.folder_path

				self.window.show_quick_panel(name_of_folders, self.selectFolder)
			else:
				self.install_on_folder = self.folder_path[0]
				downloadLib(self.install_on_folder, self.selected_lib)

	def selectFolder(self, folder_index):
		self.install_on_folder = self.folder_path[folder_index]
		downloadLib(self.install_on_folder, self.selected_lib)



class SearchLibrary(sublime_plugin.TextCommand):
	def __init__(self, view):
		self.view = view
		self.window = sublime.active_window()
		self.result_arr = []
		self.result_arr_list = []
		self.lib_versions = []
		self.searchURL = 'https://api.cdnjs.com/libraries?search='
		self.install_on_folder = ''

	def run(self, edit):
		self.window.show_input_panel("Search for:", "", self.searchTerm, None, None)


	def searchTerm(self, term):
		if term:
			search_req = httpGet(self.searchURL + term + '&fields=version,description').read().decode('utf-8')
			get_results = json.loads(search_req)['results']

			for lib in get_results:
				self.result_arr.append(lib['name'])
				self.result_arr_list.append([lib['name'],lib['name'] + '-' + lib['version'],lib['description']])

			self.window.show_quick_panel(self.result_arr_list, self.selectFindedLib)

	def selectFindedLib(self, result_index):
		if result_index > -1:

			self.selected_lib = { 'search_name': self.result_arr[result_index], 'name': self.result_arr[result_index] }

			search_t = SearchLibVersions(self.result_arr[result_index])
			search_t.start()

			self.result_arr = []
			self.result_arr_list = []


	def selectFolder(self, folder_index):
		self.install_on_folder = self.folder_path[folder_index]
		downloadLib(self.install_on_folder, self.selected_lib)
					

# get lib files via thread
class GetLibThread(threading.Thread):
	def __init__(self, selected_lib, install_on):
		self.selected_lib = selected_lib
		self.selected_lib_name = selected_lib['search_name']
		self.install_on = install_on
		self.apiRoot = 'https://api.cdnjs.com/libraries/'
		self.apiSearch = self.apiRoot + self.selected_lib_name
		self.cdnURL = 'https://cdnjs.cloudflare.com/ajax/libs/'

		threading.Thread.__init__(self)

	def run(self):
		sublime.status_message("Downloading " + self.selected_lib['name'] + "...")

		if 'dependencies' in self.selected_lib:
			for d in self.selected_lib['dependencies']:
				# for each dependency, create a new recursive thread
				selected_dep_lib = Libraries().getLibraryBySearchName(d)
				get_t = GetLibThread(selected_dep_lib, self.install_on)
				get_t.start()


		get_latest_req = httpGet(self.apiSearch).read().decode('utf-8')
		get_latest = json.loads(get_latest_req)

		if get_latest:
			# get the filename
			file_name_by_url = get_latest['filename']

			lib_folder = self.install_on + "/" + get_latest['name'] + '-' + get_latest['version']

			# create the dir
			if os.path.isdir(lib_folder) == False:
				os.mkdir(lib_folder)

				if 'assets' in get_latest:
					for asset in get_latest['assets']:
						if asset['version'] == get_latest['version']:
							for file_name in asset['files']:
								# get the latest version
								latest_url = self.cdnURL + '/'+ get_latest['name'] + '/' + get_latest['version'] + '/' + file_name
								
								# print(latest_url)
								file_path = lib_folder + '/' + file_name
								new_f_t = newFileThread(latest_url, file_path, file_name)
								new_f_t.start()

# get lib files via thread
class GetLibVersionThread(threading.Thread):
	def __init__(self, selected_lib, install_on, version):
		self.selected_lib = selected_lib
		self.install_on = install_on
		self.target_version = version
		self.apiRoot = 'https://api.cdnjs.com/libraries/'
		self.apiSearch = self.apiRoot + self.selected_lib
		self.cdnURL = 'https://cdnjs.cloudflare.com/ajax/libs/'

		threading.Thread.__init__(self)

	def run(self):
		sublime.status_message("Downloading " + self.selected_lib + "...")

		settings = sublime.load_settings("AddLibrary.sublime-settings") 
		default_lib = settings.get("default_folder")

		get_lib_req = httpGet(self.apiSearch).read().decode('utf-8')
		lib_list = json.loads(get_lib_req)

		# folder that lib will be
		lib_folder = self.install_on + default_lib + "/" + self.selected_lib + '-' + self.target_version

		if os.path.isdir(self.install_on + default_lib) == False:
			os.mkdir(self.install_on + default_lib)

		if os.path.isdir(lib_folder) == False:
			os.mkdir(lib_folder)

		for assets in lib_list['assets']:
			if assets['version'] == self.target_version:
				for file_name in assets['files']:
					# get the latest version
					file_url = self.cdnURL + '/'+ self.selected_lib + '/' + self.target_version + '/' + file_name
					
					file_path = lib_folder + '/' + file_name
					new_f_t = newFileThread(file_url, file_path, file_name)
					new_f_t.start()


							
# create a file via thread		
class newFileThread(threading.Thread):
	def __init__(self, url_to_content, file_path, file_name):
		self.url_to_content = url_to_content
		self.file_path = file_path
		self.file_name = file_name
		threading.Thread.__init__(self)

	def run(self):
		file_content = httpGet(self.url_to_content).read().decode('utf-8')
		directory = os.path.dirname(self.file_path)

		if not os.path.exists(directory):
			os.makedirs(directory)
			
		# create the file
		new_file = os.open( self.file_path, os.O_RDWR|os.O_CREAT )
		os.write( new_file, file_content.encode('utf-8') )
		os.close( new_file )

		sublime.status_message("File downloaded: " + self.file_name)

class SearchLibVersions(threading.Thread):
	def __init__(self, lib_name):
		self.lib_name = lib_name
		self.libraryURL = 'https://api.cdnjs.com/libraries/'
		self.window = sublime.active_window()
		self.folder_path = self.window.folders()
		self.list_versions = []
		threading.Thread.__init__(self)

	def run(self):
		versions_req = httpGet(self.libraryURL + self.lib_name).read().decode('utf-8')
		self.lib_versions = json.loads(versions_req)
		self.list_lib_versions = []
		for version in self.lib_versions['assets']:
			self.list_versions.append([ self.lib_versions['name'] + ' - version '+version['version'] ])
			self.list_lib_versions.append(version['version'])

		self.window.show_quick_panel(self.list_versions, self.installLibByVersion)

	
	def installLibByVersion(self, selected_version_index):
		if selected_version_index > -1:
			selected_version = self.list_lib_versions[selected_version_index]

		self.folder_path = self.window.folders()
		
		# if have more than a active folder in sublime
		if len(self.folder_path) > 1:
			name_of_folders = self.folder_path

			self.window.show_quick_panel(name_of_folders, self.selectFolder)
		else:
			self.install_on_folder = self.folder_path[0]
			get_version_t = GetLibVersionThread(self.lib_name, self.install_on_folder, selected_version )
			get_version_t.start()

	def selectFolder(self, folder_index):
		self.install_on_folder = self.folder_path[folder_index]
		get_version_t = GetLibVersionThread(self.lib_name, self.install_on_folder, selected_version )
		get_version_t.start()
			
