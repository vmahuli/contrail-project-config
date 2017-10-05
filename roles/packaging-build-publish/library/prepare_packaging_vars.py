#!/usr/bin/python

import os
import re

from ansible.module_utils.basic import AnsibleModule

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: prepare_packaging_vars

short_description: Prepare variables describing package being built.

description:
  - "This module prepares a number of variables that describe package that is being built,
for example upstream version, package version, source location, and workspace layout."

options:
  packaging_repo: Zuul dictionary with packaging project information.

  source_repo: An optional Zuul object for upstream source project. If not given, module will try to locate it based on the packaging repo.

author:
  - OpenContrail Developers <dev@lists.opencontrail.org>
'''


def _debian_get_name_versions(changelog_path):
    '''Returns tuple (package_name (epoch, upstream_version, debian_version)) based on changelog'''
    if not os.path.exists(changelog_path):
        raise RuntimeError("changelog is missing at %s" % (changelog_path,))
    with open(changelog_path, "r") as fh:
        manifest = fh.readline()

    matcher = "^(?P<name>[\w-]+)\ \((?P<version>.*)\).*$"
    groups = re.match(matcher, manifest)
    if not groups:
        raise RuntimeError("Could not parse debian/changelog")
    return groups.group(1), groups.group(2)



def get_package_name_versions(module):
    """Returns a dictionary with package information."""
    params = module.params

    src_dir = params['packaging_repo']['src_dir']
    if not os.path.exists(src_dir):
        raise RuntimeError("Could not find packaging repository under %s" % (src_dir,))

    distro = params['distribution']
    release = params['release']
    if distro == "ubuntu":
        debian_path = os.path.join(src_dir, distro, release, "debian/")
        changelog_path = os.path.join(debian_path, "changelog")

        package_name, version = _debian_get_name_versions(changelog_path)

        try:
            (epoch, rest) = version.split(":")
        except ValueError:
            epoch, rest = None, version

        upstream, debian = rest.split('-')

        return {
            'name': package_name,
            'full_version': version,
            'version': {
                'epoch': epoch,
                'upstream': upstream,
                'distro': debian
            }
        }

    else:
        raise RuntimeError("Unsupported distribution: %s" % (distro,))


def get_upstream_path(module):
    packaging_repo, upstream_repo = module.params['packaging_repo'], module.params['source_repo']
    package = get_package_name_versions(module)

    if upstream_repo:
        local_path = upstream_repo['src_dir']
    else:
        # deduce local_path based on packaging_repository
        # XXX: This assumes that both packaging repository and upstream source are pulled from
        #      the same zuul connection.
        packaging_path = packaging_repo['src_dir']
        print "packaging_path: %s" % (packaging_path,)
        packaging_short_name = packaging_repo['short_name']
        print "packaging_short_name: %s" % (packaging_short_name,)

        upstream_repo_name = packaging_short_name.lstrip("packaging-")
        print "upstream_repo_name: %s" % (upstream_repo_name,)
        packaging_org_dir = "/".join(packaging_path.split("/")[:-1])
        print "packaging_org_dir: %s" % (packaging_org_dir,)

        local_path = os.path.join(packaging_org_dir, upstream_repo_name)
        print "local_path: %s" % (local_path,)
        if not os.path.exists(local_path):
            local_path = None
    target_path = "%s-%s" % (package['name'], package['version']['upstream'])

    if local_path is None:
        return None

    return {"source_dir": local_path, "target_path": target_path}


result = dict(
    changed=False,
    original_message='',
    message='',
)

def main(testing=False):
    module = AnsibleModule(
        argument_spec=dict(
            packaging_repo=dict(type='dict', required=True),
            source_repo=dict(type='dict', required=False, default=None),
            distribution=dict(type='str', required=True),
            release=dict(type='str', required=True),
        ),
    )

    try:
        result['package'] = get_package_name_versions(module)
        upstream_source = get_upstream_path(module)
        if upstream_source:
            result['upstream'] = upstream_source
    except RuntimeError as e:
        module.fail_json(msg=e.message, **result)

    module.exit_json(**result)

if __name__ == '__main__':
    main(testing=True)