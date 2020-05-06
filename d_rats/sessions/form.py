from __future__ import absolute_import
from d_rats.sessions import base, file

class FormTransferSession(file.FileTransferSession):
    type = base.T_FORMXFER
