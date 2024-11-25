#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from time import sleep

"""
Simple script to gather some data about a disk to verify it's seen by the OS
and is properly represented.  Defaults to sda if not passed a disk at run time

Usage:
    python disk_stats_test.py [-h] [--disk-name DISK_NAME]
"""


class Disk:
    def __init__(self, disk_name="sda", status=0):
        """
        Initialize the disk validator class

        Args:
            disk_name (str): The disk to collect statistics from
            status (int): Exit status for NVDIMM validation
        """
        self.disk_name = disk_name
        self.status = status

    def check_return_code(self, return_code, err_message):
        """
        Error handling during validation check

        Args:
            return_code (int): The return code from the function
            err_message (str): The error message to print
        """
        if return_code != 0:
            print(err_message, file=sys.stderr)
            sys.exit(1)

    def is_nvdimm(self):
        """Validate if disk is NVDIMM"""
        nvdimm = "pmem"
        if nvdimm in self.disk_name:
            print(
                f"Disk {self.disk_name} appears to be an NVDIMM, skipping",
                file=sys.stderr,
            )
            sys.exit(self.status)

    def disk_in_file(self, file_path, message):
        """Validate disk exists in file"""
        try:
            with open(file_path) as file:
                for line in file:
                    if self.disk_name in line:
                        return True
            self.check_return_code(1, message)
        except FileNotFoundError:
            self.check_return_code(1, f"Error: {file_path} not found")

    def block_exists(self):
        """Validate block device exists"""
        block_path = f"/sys/block/{self.disk_name}"
        if os.path.exists(block_path):
            return True
        else:
            self.check_return_code(
                1, f"Disk {self.disk_name} not found in /sys/block"
            )

    def block_stat_not_empty(self):
        """Validate if there are statistic for disk"""
        stats_file = f"/sys/block/{self.disk_name}/stat"
        try:
            if os.path.getsize(stats_file) > 0:
                return True
            else:
                self.check_return_code(
                    1,
                    f"stat is either empty or nonexistant in {stats_file}",
                )
        except FileNotFoundError:
            self.check_return_code(1, f"Error: {stats_file} not found")

    def run_validate(self):
        """Run all validation for disk"""
        file_handling = {
            "/proc/partitions": f"Disk {self.disk_name} not found in ",
            "/proc/diskstats": f"Disk {self.disk_name} not found in ",
        }

        self.is_nvdimm()
        for file_path, msg in file_handling.items():
            message = msg + file_path
            self.disk_in_file(file_path, message)
        self.block_exists()
        self.block_stat_not_empty()

    def proc_stats(self):
        """Collect statistics from /proc/diskstats"""
        with open("/proc/diskstats") as file:
            for line in file:
                if self.disk_name in line:
                    return line

    def sys_stats(self):
        """Collect statistics from/sys/block/*disk*/stat"""
        file_path = f"/sys/block/{self.disk_name}/stat"
        with open(file_path) as file:
            return file.read()

    def generate_activity(self):
        """Generate activity in disk using Linux utility"""

        command = ["hdparm", "-t", f"/dev/{self.disk_name}"]

        try:
            result = subprocess.run(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if result.returncode != 0:
                self.check_return_code(1, "ERROR: hdparm execution failed")
        except FileNotFoundError:
            self.check_return_code(
                1, "ERROR: hdparm not found, please install before retrying"
            )

    def collect_statistics(self):
        """Collect statistics from disk"""
        proc_stat_begin = self.proc_stats()
        sys_stat_begin = self.sys_stats()

        self.generate_activity()

        sleep(5)

        proc_stat_end = self.proc_stats()
        sys_stat_end = self.sys_stats()

        if proc_stat_begin == proc_stat_end:
            self.check_return_code(
                1, "Stats in /proc/diskstats did not change"
            )
        elif sys_stat_begin == sys_stat_end:
            self.check_return_code(
                1, f"Stats in /sys/block/{self.disk_name}/stat did not change"
            )
        else:
            print(f"PASS: Finished testing stats for {self.disk_name}")


def main():
    """Main function to execute the program."""
    parser = argparse.ArgumentParser(description="Retrieve disk statistics.")
    parser.add_argument(
        "--disk-name",
        required=False,
        help="Disk to analyze statistics. Defaults to 'sda'",
        default="sda",
    )

    args = parser.parse_args()

    # Retrieving disk name and removing /dev/ if it exists for consistency
    disk_name = args.disk_name.strip("/dev/")

    disk = Disk(disk_name=disk_name)
    disk.run_validate()
    disk.collect_statistics()


if __name__ == "__main__":
    main()
