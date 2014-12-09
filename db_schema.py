# -*- coding: utf-8 -*-

import sys

from obesho_back import Base, engine


def main(_):
    Base.metadata.create_all(engine)


if __name__ == '__main__':
    sys.exit(main(sys.argv[0:]))
