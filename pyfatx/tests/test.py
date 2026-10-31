#!/usr/bin/env python3
import functools
import os
import tempfile
import unittest
import random

from pyfatx import Fatx, ffi
from pyfatx import fatx_close_dir, fatx_get_attr, fatx_next_dir_entry, fatx_open_dir, fatx_read_dir, fatx_write_dir


def with_formatted_disk(func):
	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
			hdd_img_path = tmp_file.name + "-fatx"
		try:
			Fatx.create(hdd_img_path)
			return func(*args, hdd_img_path, **kwargs)
		finally:
			os.remove(hdd_img_path)
			os.remove(tmp_file.name)
	return wrapper


class BasicTest(unittest.TestCase):
	"""
	Run basic tests.
	"""

	@with_formatted_disk
	def test_read_empty_file(self, path):
		fs = Fatx(path)
		empty_file = '/empty'
		fs.mknod(empty_file)

		res = fs.read(empty_file)
		fs.unlink(empty_file)
		assert len(res) == 0

	@with_formatted_disk
	def test_create_file(self, path):
		test_file_path = '/test_file.txt'
		fs = Fatx(path)
		content = b'12345'
		fs.write(test_file_path, content)

		written = fs.read(test_file_path)
		assert written == content

		fs.unlink(test_file_path)
		file_still_available = False
		try:
			fs.get_attr(test_file_path)
			file_still_available = True
		except AssertionError:
			pass
		assert not file_still_available

	@with_formatted_disk
	def test_truncate_file(self, path):
		test_file_path = '/test_file.txt'
		fs = Fatx(path)
		content = b'12345'
		fs.write(test_file_path, content)

		fs.truncate(test_file_path, 3)

		written = fs.read(test_file_path)
		assert written == content[:3]

		fs.unlink(test_file_path)

	@with_formatted_disk
	def test_rename_file(self, path):
		test_file_path = '/test_file.txt'
		fs = Fatx(path)
		content = b'12345'
		fs.write(test_file_path, content)

		new_filename = '/renamed_test_file.txt'
		fs.rename(test_file_path, new_filename)

		original_file_still_available = False
		try:
			fs.get_attr(test_file_path)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		fs.unlink(new_filename)

	@with_formatted_disk
	def test_write_large_file(self, path):
		test_file_path = '/largefile'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)
		b = bytes([rng.getrandbits(8) for _ in range(1024 * 1024)])
		
		fs.write(test_file_path, b)

		d = fs.read(test_file_path)
		fs.unlink(test_file_path)

		assert d == b

	
	@with_formatted_disk
	def test_write_offset(self, path):
		test_file_path = '/offsetfile'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		# Write 1KB of random data
		b = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file_path, b)

		# Delete the data
		d = fs.read(test_file_path)
		fs.unlink(test_file_path)
		assert d == b

		# Write 512KB of random data at offset 128
		b = bytes([rng.getrandbits(8) for _ in range(1024 * 512)])
		fs.write(test_file_path, b, offset=128)

		# Read from offset zero
		d = fs.read(test_file_path)
		fs.unlink(test_file_path)

		assert d == bytes([0] * 128) + b


	@with_formatted_disk
	def test_rename_overwrite(self, path):
		test_file1 = '/test_overwrite1'
		test_file2 = '/test_overwrite2'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		# file1 should be above file2 in the dirent list
		# so this tests that overwriting file1 removes it
		fs.rename(test_file2, test_file1)

		d = fs.read(test_file1)
		fs.unlink(test_file1)

		original_file_still_available = False
		try:
			fs.get_attr(test_file2)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		assert d == b2


	@with_formatted_disk
	def test_rename_exchange(self, path):
		test_file1 = '/test_xchg1'
		test_file2 = '/test_xchg2'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		fs.rename(test_file2, test_file1, exchange=True)

		d1 = fs.read(test_file1)
		d2 = fs.read(test_file2)

		fs.unlink(test_file1)
		fs.unlink(test_file2)

		assert d1 == b2
		assert d2 == b1


	@with_formatted_disk
	def test_rename_exchange_different_dirname_overwrite(self, path):
		test_file1 = '/test_xchg1'
		file2_dir = '/testdir'
		test_file2 = '{}/test_xchg2'.format(file2_dir)
		fs = Fatx(path)

		fs.mkdir(file2_dir)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		fs.rename(test_file2, test_file1, exchange=True)

		d1 = fs.read(test_file1)
		d2 = fs.read(test_file2)

		fs.unlink(test_file1)
		fs.unlink(test_file2)
		
		fs.rmdir(file2_dir)

		assert d1 == b2
		assert d2 == b1


	@with_formatted_disk
	def test_rename_different_dirname_overwrite(self, path):
		test_file1 = '/test_xchg1'
		file2_dir = '/testdir'
		test_file2 = '{}/test_xchg2'.format(file2_dir)
		fs = Fatx(path)

		fs.mkdir(file2_dir)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		fs.rename(test_file2, test_file1)

		d1 = fs.read(test_file1)
		fs.unlink(test_file1)

		fs.rmdir(file2_dir)

		original_file_still_available = False
		try:
			fs.get_attr(test_file2)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		assert d1 == b2


	@with_formatted_disk
	def test_rename_different_dirname_nonexisting(self, path):
		test_file1 = '/test_xchg1'
		file2_dir = '/testdir'
		test_file2 = '{}/test_xchg2'.format(file2_dir)
		fs = Fatx(path)

		fs.mkdir(file2_dir)

		rng = random.Random()
		rng.seed(12345)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		fs.rename(test_file2, test_file1)

		d1 = fs.read(test_file1)
		fs.unlink(test_file1)

		fs.rmdir(file2_dir)

		original_file_still_available = False
		try:
			fs.get_attr(test_file2)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		assert d1 == b2


	@with_formatted_disk
	def test_rename_no_replace_different_dirname_nonexisting(self, path):
		test_file1 = '/test_xchg1'
		file2_dir = '/testdir'
		test_file2 = '{}/test_xchg2'.format(file2_dir)
		fs = Fatx(path)

		fs.mkdir(file2_dir)

		rng = random.Random()
		rng.seed(12345)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		fs.rename(test_file2, test_file1, no_replace=True)

		d1 = fs.read(test_file1)
		fs.unlink(test_file1)

		fs.rmdir(file2_dir)

		original_file_still_available = False
		try:
			fs.get_attr(test_file2)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		assert d1 == b2


	@with_formatted_disk
	def test_rename_no_replace_different_dirname_existing_fails(self, path):
		test_file1 = '/test_xchg1'
		file2_dir = '/testdir'
		test_file2 = '{}/test_xchg2'.format(file2_dir)
		fs = Fatx(path)

		fs.mkdir(file2_dir)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		rename_failed = False
		try:
			fs.rename(test_file2, test_file1, no_replace=True)
			rename_failed = True
		except AssertionError:
			pass

		fs.unlink(test_file1)
		fs.unlink(test_file2)

		fs.rmdir(file2_dir)

		assert not rename_failed


	@with_formatted_disk
	def test_rename_exchange_nonexistent_file_fails(self, path):
		test_file1 = '/test_xchg1'
		test_file2 = '/test_xchg2'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		rename_failed = False
		try:
			fs.rename(test_file1, test_file2, exchange=True)
			rename_failed = True
		except AssertionError:
			pass

		if rename_failed:
			fs.unlink(test_file2)
		else:
			fs.unlink(test_file1)

		assert not rename_failed


	@with_formatted_disk
	def test_rename_no_replace_does_not_replace_file(self, path):
		test_file1 = '/test_xchg1'
		test_file2 = '/test_xchg2'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		rename_failed = False
		try:
			fs.rename(test_file2, test_file1, no_replace=True)
			rename_failed = True
		except AssertionError:
			pass

		fs.unlink(test_file1)
		fs.unlink(test_file2)

		assert not rename_failed


	@with_formatted_disk
	def test_rename_no_replace_with_nonexistent_destination_works(self, path):
		test_file1 = '/test_xchg1'
		test_file2 = '/test_xchg2'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		fs.rename(test_file1, test_file2, no_replace=True)

		d2 = fs.read(test_file2)

		fs.unlink(test_file2)

		original_file_still_available = False
		try:
			fs.get_attr(test_file1)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		assert d2 == b1


	@with_formatted_disk
	def test_filename_max_length(self, path):
		fs = Fatx(path)

		# 42 characters is the longest name a FATX directory entry holds
		name42 = '/' + 'a' * 38 + '.bin'
		fs.write(name42, b'42')
		assert fs.read(name42) == b'42'
		assert [a.filename for a in fs.listdir('/')] == [name42[1:]]

		renamed42 = '/' + 'b' * 38 + '.bin'
		fs.rename(name42, renamed42)
		assert fs.read(renamed42) == b'42'

		name43 = '/' + 'c' * 39 + '.bin'
		created = False
		try:
			fs.write(name43, b'43')
			created = True
		except AssertionError:
			pass
		assert not created

		fs.unlink(renamed42)


	@with_formatted_disk
	def test_directory_grows_past_one_cluster(self, path):
		fs = Fatx(path)

		# Created back to back, so the directory cluster of /neighbor follows
		# the first directory cluster of /big on disk.
		fs.mkdir('/big')
		fs.mkdir('/neighbor')

		rng = random.Random()
		rng.seed(12345)
		canary = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write('/neighbor/canary', canary)

		# 600 entries span three 16 KiB directory clusters (256 entries each)
		count = 600
		for i in range(count):
			fs.write('/big/file{:04d}'.format(i), 'file {}'.format(i).encode())

		names = sorted(a.filename for a in fs.listdir('/big'))
		assert names == ['file{:04d}'.format(i) for i in range(count)]

		for i in range(count):
			assert fs.read('/big/file{:04d}'.format(i)) == 'file {}'.format(i).encode()

		assert [a.filename for a in fs.listdir('/neighbor')] == ['canary']
		assert fs.read('/neighbor/canary') == canary

		# A freed slot in a later cluster is reused
		fs.unlink('/big/file0500')
		fs.write('/big/file0500', b'again')
		assert fs.read('/big/file0500') == b'again'

		for i in range(count):
			fs.unlink('/big/file{:04d}'.format(i))
		fs.rmdir('/big')


	@with_formatted_disk
	def test_directory_with_full_last_cluster(self, path):
		# FATX_STATUS_* values from libfatx/fatx.h
		STATUS_FILE_NOT_FOUND = -2
		STATUS_END_OF_DIR = 2

		fs = Fatx(path)
		fs.mkdir('/full')

		# 255 entries fill all but the last slot of the first 16 KiB cluster,
		# which then holds the end-of-directory marker.
		for i in range(255):
			fs.write('/full/f{:03d}'.format(i), b'x')

		# Overwrite that marker with a 256th entry. The directory's only
		# cluster is now full with no end marker, the state left on disk by
		# writers that fill the last slot without extending the chain. The
		# entry borrows the cluster of /donor; neither file is written again.
		fs.write('/donor', b'y')
		attr = ffi.new('struct fatx_attr *')
		assert fatx_get_attr(fs.fs, b'/donor', attr) == 0
		attr.filename = b'f255'
		dirent = ffi.new('struct fatx_dirent *')
		dirent.filename = b'f255'
		d = ffi.new('struct fatx_dir *')
		assert fatx_open_dir(fs.fs, b'/full', d) == 0
		d.entry = 255
		assert fatx_write_dir(fs.fs, d, dirent, attr) == 0
		assert fatx_close_dir(fs.fs, d) == 0

		# Walking the directory reaches its end, not an error
		d = ffi.new('struct fatx_dir *')
		result = ffi.new('struct fatx_dirent **')
		assert fatx_open_dir(fs.fs, b'/full', d) == 0
		names = []
		while True:
			assert fatx_read_dir(fs.fs, d, dirent, attr, result) == 0
			names.append(ffi.string(dirent.filename).decode('ascii'))
			s = fatx_next_dir_entry(fs.fs, d)
			if s != 0:
				break
		assert fatx_close_dir(fs.fs, d) == 0
		assert s == STATUS_END_OF_DIR
		assert names == ['f{:03d}'.format(i) for i in range(256)]

		# A missing name is reported as not found, not as an error
		assert fatx_get_attr(fs.fs, b'/full/missing', attr) == STATUS_FILE_NOT_FOUND

		# The directory grows from this state and keeps its entries
		fs.write('/full/one_more', b'z')
		assert fs.read('/full/one_more') == b'z'
		names = sorted(a.filename for a in fs.listdir('/full'))
		assert names == sorted(['f{:03d}'.format(i) for i in range(256)] + ['one_more'])
		assert fs.read('/full/f000') == b'x'


	@with_formatted_disk
	def test_path_component_does_not_match_longer_sibling(self, path):
		fs = Fatx(path)

		# '/Game 2' is created first, so a lookup of the intermediate
		# component 'Game/' that matched by prefix would resolve to it.
		fs.mkdir('/Game 2')
		fs.mkdir('/Game 2/video')
		fs.write('/Game 2/video/a.txt', b'two')
		fs.mkdir('/Game')
		fs.mkdir('/Game/video')
		fs.write('/Game/video/b.txt', b'one')

		assert [a.filename for a in fs.listdir('/Game 2/video')] == ['a.txt']
		assert [a.filename for a in fs.listdir('/Game/video')] == ['b.txt']
		assert fs.read('/Game 2/video/a.txt') == b'two'
		assert fs.read('/Game/video/b.txt') == b'one'


	@with_formatted_disk
	def test_path_component_prefix_is_not_found(self, path):
		fs = Fatx(path)
		fs.mkdir('/top')
		fs.mkdir('/top/wolf')
		fs.mkdir('/top/wolf/inner')
		fs.write('/top/wolf/inner/x', b'x')

		# Prefixes of an existing directory name, used as intermediate
		# components, are not that directory
		for missing in ('/top/w/inner/x', '/top/wol/inner/x'):
			found = False
			try:
				fs.get_attr(missing)
				found = True
			except AssertionError:
				pass
			assert not found, missing

		assert fs.read('/top/wolf/inner/x') == b'x'


if __name__ == '__main__':
	unittest.main()
