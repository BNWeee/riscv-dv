"""
Copyright 2019 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Parse the regression testlist in YAML format
"""

import os
import random
import sys
import re
import subprocess
import time
import yaml
import logging

from datetime import date

RET_SUCCESS = 0
RET_FAIL    = 1
RET_FATAL   = -1

def setup_logging(verbose):
  """Setup the root logger.

  Args:
    verbose: Verbose logging
  """
  if verbose:
    logging.basicConfig(format="%(asctime)s %(filename)s:%(lineno)-5s %(levelname)-8s %(message)s",
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        level=logging.DEBUG)
  else:
    logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s",
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        level=logging.INFO)


def read_yaml(yaml_file):
  """ Read YAML file to a dictionary

  Args:
    yaml_file : YAML file

  Returns:
    yaml_data : data read from YAML in dictionary format
  """
  with open(yaml_file, "r") as f:
    try:
      yaml_data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
      logging.error(exc)
      sys.exit(RET_FAIL)
  return yaml_data


def get_env_var(var):
  """Get the value of environment variable

  Args:
    var : Name of the environment variable

  Returns:
    val : Value of the environment variable
  """
  try:
    val = os.environ[var]
  except KeyError:
    logging.warning("Please set the environment variable %0s" % var)
    sys.exit(RET_FAIL)
  return val


def get_seed(seed):
  """Get the seed to run the generator

  Args:
    seed : input seed

  Returns:
    seed to run instruction generator
  """
  if seed >= 0:
    return seed
  else:
    return random.getrandbits(32)


def run_cmd(cmd, timeout_s = 999, exit_on_error = 1, check_return_code = True):
  """Run a command and return output

  Args:
    cmd : shell command to run

  Returns:
    command output
  """
  logging.debug(cmd)
  try:
    ps = subprocess.Popen("exec " + cmd,
                          shell=True,
                          executable='/bin/bash',
                          universal_newlines=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
  except subprocess.CalledProcessError as exc:
    logging.error(ps.communicate()[0])
    sys.exit(RET_FAIL)
  try:
    output = ps.communicate(timeout = timeout_s)[0]
  except subprocess.TimeoutExpired:
    logging.error("Timeout[%ds]: %s" % (timeout_s, cmd))
    output = ""
    ps.kill()
  rc = ps.returncode
  if rc and check_return_code and rc > 0:
    logging.info(output)
    logging.error("ERROR return code: %d/%d, cmd:%s" % (check_return_code, rc, cmd))
    if exit_on_error:
      sys.exit(RET_FAIL)
  logging.debug(output)
  return output


def run_parallel_cmd(cmd_list, timeout_s = 999, exit_on_error = 0, check_return_code = True):
  """Run a list of commands in parallel

  Args:
    cmd_list: command list

  Returns:
    command output
  """
  children = []
  for cmd in cmd_list:
    ps = subprocess.Popen("exec " + cmd,
                          shell=True,
                          executable='/bin/bash',
                          universal_newlines=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    children.append(ps)
  for i in range(len(children)):
    logging.info("Command progress: %d/%d" % (i, len(children)))
    logging.debug("Waiting for command: %s" % cmd_list[i])
    try:
      output = children[i].communicate(timeout = timeout_s)[0]
    except subprocess.TimeoutExpired:
      logging.error("Timeout[%ds]: %s" % (timeout_s, cmd))
      children[i].kill()
    rc = children[i].returncode
    if rc and check_return_code and rc > 0:
      logging.info(output)
      logging.error("ERROR return code: %d, cmd:%s" % (rc, cmd))
      if exit_on_error:
        sys.exit(RET_FAIL)
    # Restore stty setting otherwise the terminal may go crazy
    os.system("stty sane")
    logging.debug(output)


def process_regression_list(testlist, test, iterations, matched_list, riscv_dv_root):
  """ Get the matched tests from the regression test list

  Args:
    testlist      : Regression test list
    test          : Test to run, "all" means all tests in the list
    iterations    : Number of iterations for each test
    riscv_dv_root : Root directory of RISCV-DV

  Returns:
    matched_list : A list of matched tests
  """
  logging.info("Processing regression test list : %s, test: %s" % (testlist, test))
  yaml_data = read_yaml(testlist)
  mult_test = test.split(',')
  for entry in yaml_data:
    if 'import' in entry:
      sub_list = re.sub('<riscv_dv_root>', riscv_dv_root, entry['import'])
      process_regression_list(sub_list, test, iterations, matched_list, riscv_dv_root)
    else:
      if (entry['test'] in mult_test) or (test == "all"):
        if (iterations > 0 and  entry['iterations'] > 0):
          entry['iterations'] = iterations
        if entry['iterations'] > 0:
          logging.info("Found matched tests: %s, iterations:%0d" %
                      (entry['test'], entry['iterations']))
          matched_list.append(entry)

def create_output(output, prefix = "out_"):
  """ Create output directory

  Args:
    output : Name of specified output directory

  Returns:
    Output directory
  """
  # Create output directory
  if output is None:
    return prefix + str(date.today())
  else:
    return output
