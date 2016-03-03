# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Tests for S3 downloader"""

import os
from mock import patch

from ..s3 import S3Authenticator
from ..providers import Providers, Credential  # to test against crcns

from ...tests.utils import swallow_outputs
from ...tests.utils import SkipTest
from ...tests.utils import with_tempfile
from ...tests.utils import assert_equal
from ...tests.utils import assert_in
from ...tests.utils import use_cassette
from ...tests.utils import assert_raises
from ...dochelpers import exc_str
from ...downloaders.base import DownloadError

try:
    import boto
except Exception as e:
    raise SkipTest("boto module is not available: %s" % exc_str(e))

from .utils import get_test_providers
from .test_http import check_download_external_url
from datalad.downloaders.tests.utils import get_test_providers

url_2versions_nonversioned1 = 's3://datalad-test0-versioned/2versions-nonversioned1.txt'
url_2versions_nonversioned1_ver1 = url_2versions_nonversioned1 + '?versionId=null'
url_2versions_nonversioned1_ver2 = url_2versions_nonversioned1 + '?versionId=V4Dqhu0QTEtxmvoNkCHGrjVZVomR1Ryo'

# TODO: I think record_mode='all' must not be necessary here but something makes interaction
# different across runs
@use_cassette('fixtures/vcr_cassettes/test_s3_download_basic.yaml', record_mode='all')
def test_s3_download_basic():

    for url, success_str, failed_str in [
        (url_2versions_nonversioned1, 'version2', 'version1'),
        (url_2versions_nonversioned1_ver2, 'version2', 'version1'),
        (url_2versions_nonversioned1_ver1, 'version1', 'version2'),
    ]:
        yield check_download_external_url, url, failed_str, success_str
test_s3_download_basic.tags = ['network']


# TODO: redo smart way with mocking, to avoid unnecessary CPU waste
@use_cassette('test_s3_mtime')
@with_tempfile
def test_mtime(tempfile):
    url = url_2versions_nonversioned1_ver2
    with swallow_outputs():
        get_test_providers(url).download(url, path=tempfile)
    assert_equal(os.stat(tempfile).st_mtime, 1446873817)

    # and if url is wrong
    url = 's3://datalad-test0-versioned/nonexisting'
    assert_raises(DownloadError, get_test_providers(url).download, url, path=tempfile, overwrite=True)


@use_cassette('test_s3_reuse_session')
@with_tempfile
# forgot how to tell it not to change return value, so this side_effect beast now
@patch.object(S3Authenticator, 'authenticate', side_effect=S3Authenticator.authenticate, autospec=True)
def test_reuse_session(tempfile, mocked_auth):
    Providers.reset_default_providers()  # necessary for the testing below
    providers = get_test_providers(url_2versions_nonversioned1_ver1)  # to check credentials
    with swallow_outputs():
        providers.download(url_2versions_nonversioned1_ver1, path=tempfile)
    assert_equal(mocked_auth.call_count, 1)

    providers2 = Providers.from_config_files()
    with swallow_outputs():
        providers2.download(url_2versions_nonversioned1_ver2, path=tempfile, overwrite=True)
    assert_equal(mocked_auth.call_count, 1)

    # but if we reload -- everything reloads and we need to authenticate again
    providers2 = Providers.from_config_files(reload=True)
    with swallow_outputs():
        providers2.download(url_2versions_nonversioned1_ver2, path=tempfile, overwrite=True)
    assert_equal(mocked_auth.call_count, 2)